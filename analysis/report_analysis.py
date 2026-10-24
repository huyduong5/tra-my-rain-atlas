#!/usr/bin/env python3
"""
Tính toán số liệu cho báo cáo LaTeX — mưa giờ trạm Trà My 2008–2017.

Sinh ra:
  bao_cao_latex/tables/*.tex     phần thân bảng (các hàng), header/caption nằm trong sections/
  bao_cao_latex/figures/*.png    hình minh họa
  outputs/report/report_numbers.json   các con số dùng trong phần nhận xét
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from analyze_tra_my import (
    CSV_PATH,
    build_daily,
    compute_rx,
    gumbel_from_lmoments,
    gev_from_lmoments,
    load_hourly,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "bao_cao_latex"
if not TEX.exists() and (ROOT.parent / "bao-cao").exists():  # bố cục repo: báo cáo ở bao-cao/
    TEX = ROOT.parent / "bao-cao"
TABLES = TEX / "tables"
FIGS = TEX / "figures"
NUM_PATH = ROOT / "outputs" / "report" / "report_numbers.json"

WET = 1.0
MONTH_VALID_FRAC = 0.90
RAINY = [9, 10, 11, 12]
DRY = [1, 2, 3, 4, 5, 6, 7, 8]
YEARS = list(range(2008, 2018))
TS = [100, 50, 20, 10]
N_BOOT = 2000
RNG = np.random.default_rng(2026)

C_SEA = "#1b4b63"
C_RAIN = "#3a7ca5"
C_SOFT = "#9cc3d9"
C_ORANGE = "#c45c26"
C_GOLD = "#d9a441"
C_DARK = "#0b1c24"

N: dict = {}


# ---------------------------------------------------------------------------
# Định dạng
# ---------------------------------------------------------------------------
def isnum(x) -> bool:
    return x is not None and not (isinstance(x, (float, np.floating)) and not np.isfinite(x))


def vn(x, nd: int = 1) -> str:
    """Số kiểu Việt Nam: dấu phẩy thập phân, cách nghìn bằng \\,."""
    if not isnum(x) or pd.isna(x):
        return "---"
    s = f"{abs(float(x)):,.{nd}f}"
    s = s.replace(",", "@").replace(".", ",").replace("@", "\\,")
    return ("$-$" + s) if float(x) < 0 and float(s.replace("\\,", "").replace(",", ".")) != 0 else s


def fv(x, nd: int = 1) -> str:
    """Số trong nhãn hình: dấu phẩy thập phân."""
    return f"{x:.{nd}f}".replace(".", ",")


def vn_date(ts) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


def vn_dm(ts) -> str:
    return pd.Timestamp(ts).strftime("%d/%m")


def write_rows(name: str, rows: list) -> None:
    """Thân bảng kẻ lưới: mỗi hàng kết thúc bằng \\hline, hoặc (cells, rule) để chọn đường kẻ khác."""
    lines = []
    for r in rows:
        if isinstance(r, str):
            lines.append(r)
            continue
        cells, rule = r if isinstance(r, tuple) else (r, r"\hline")
        lines.append(" & ".join(str(c) for c in cells) + r" \\ " + rule)
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / f"{name}.tex").write_text(
        "% Sinh tự động bởi report_analysis.py — không sửa tay\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": ":",
        }
    )


def save(name: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIGS / name, dpi=300, bbox_inches="tight")
    plt.close()


def basic_stats(x: pd.Series) -> dict:
    x = pd.Series(x).dropna().astype(float)
    if len(x) == 0:
        return {"n": 0}
    mean = x.mean()
    std = x.std(ddof=1)
    return {
        "n": int(len(x)),
        "mean": mean,
        "std": std,
        "cv": 100 * std / mean if mean else np.nan,
        "median": x.median(),
        "p25": np.percentile(x, 25),
        "p75": np.percentile(x, 75),
        "p90": np.percentile(x, 90),
        "p95": np.percentile(x, 95),
        "p99": np.percentile(x, 99),
        "min": x.min(),
        "max": x.max(),
        "skew": x.skew(),
        "sum": x.sum(),
    }


def rain_stats(x: pd.Series, big: tuple[float, float]) -> dict:
    s = basic_stats(x)
    x = pd.Series(x).dropna()
    wet = x[x >= WET]
    s.update(
        {
            "n_wet": int(len(wet)),
            "freq_wet": 100 * len(wet) / len(x),
            "mean_wet": wet.mean(),
            "median_wet": wet.median(),
            "n_big1": int((x > big[0]).sum()),
            "n_big2": int((x > big[1]).sum()),
        }
    )
    return s


# ---------------------------------------------------------------------------
# Phase 0 — dữ liệu và quy tắc hợp lệ
# ---------------------------------------------------------------------------
def prepare():
    hourly = load_hourly(CSV_PATH)
    hourly["season"] = np.where(hourly["month"].isin(RAINY), "mua", "kho")
    daily = build_daily(hourly)
    daily["season"] = np.where(daily["month"].isin(RAINY), "mua", "kho")

    # Tháng hợp lệ: >= 90% ngày hợp lệ
    mon = daily.groupby(["year", "month"]).agg(
        n_days=("valid", "size"),
        n_valid=("valid", "sum"),
        rain=("rain_mm", "sum"),
        n_wet=("wet", "sum"),
    ).reset_index()
    mon["frac"] = mon["n_valid"] / mon["n_days"]
    mon["valid"] = mon["frac"] >= MONTH_VALID_FRAC
    return hourly, daily, mon


def check_missing_pattern(hourly, daily) -> None:
    inv = daily[~daily["valid"]]
    day1 = inv[inv["date"].dt.day == 1]
    full_missing = daily[daily["n_valid"] == 0]
    # các đợt thiếu liên tục
    runs = []
    cur = None
    for d in inv["date"].sort_values():
        if cur and (d - cur[1]).days == 1:
            cur[1] = d
        else:
            if cur:
                runs.append(cur)
            cur = [d, d]
    if cur:
        runs.append(cur)
    long_runs = [(a, b, (b - a).days + 1) for a, b in runs if (b - a).days + 1 >= 5]
    # trong ngày mùng 1, các giờ thiếu là giờ nào
    h1 = hourly[(hourly["date"].dt.day == 1) & hourly["rain_mm"].isna()]
    N["missing"] = {
        "n_invalid_days": int(len(inv)),
        "n_invalid_day1": int(len(day1)),
        "n_full_missing_days": int(len(full_missing)),
        "n_month_starts": int(daily["date"].dt.day.eq(1).sum()),
        "missing_hours_day1": int(len(h1)),
        "long_runs": [
            {"start": vn_date(a), "end": vn_date(b), "days": n} for a, b, n in long_runs
        ],
        "invalid_days_other": int(len(inv) - len(day1)),
    }


# ---------------------------------------------------------------------------
# Phase 1 — Câu 1
# ---------------------------------------------------------------------------
def q1(hourly, daily, mon):
    nh = len(hourly)
    nh_ok = int(hourly["rain_mm"].notna().sum())
    nd = len(daily)
    nd_ok = int(daily["valid"].sum())
    n_mon_ok = int(mon["valid"].sum())
    year_ok = mon.groupby("year")["valid"].all()
    runs = N["missing"]["long_runs"]
    runs_txt = "; ".join(f"{r['start']}--{r['end']} ({r['days']} ngày)" for r in runs)

    N["qc"] = {
        "n_hours": nh,
        "n_hours_ok": nh_ok,
        "pct_hours_ok": 100 * nh_ok / nh,
        "n_hours_missing": nh - nh_ok,
        "pct_hours_missing": 100 * (nh - nh_ok) / nh,
        "n_days": nd,
        "n_days_ok": nd_ok,
        "pct_days_ok": 100 * nd_ok / nd,
        "n_dup": int(hourly.duplicated(["date", "hour"]).sum()),
        "n_months_ok": n_mon_ok,
        "n_years_full": int(year_ok.sum()),
        "invalid_months": [
            f"{int(r.month):02d}/{int(r.year)} ({100 * r.frac:.0f}%)"
            for r in mon[~mon["valid"]].itertuples()
        ],
        "missing_pct_by_year": {
            int(y): float(100 * g["rain_mm"].isna().mean()) for y, g in hourly.groupby("year")
        },
        "max_hour": float(hourly["rain_mm"].max()),
    }
    write_rows(
        "qc",
        [
            ["Thời đoạn số liệu", "01/01/2008 -- 31/12/2017"],
            ["Số giờ trong chuỗi", vn(nh, 0)],
            ["Số giờ có số liệu (tỉ lệ)", f"{vn(nh_ok, 0)} ({vn(100 * nh_ok / nh, 1)}\\%)"],
            ["Số giờ thiếu số liệu (tỉ lệ)", f"{vn(nh - nh_ok, 0)} ({vn(100 * (nh - nh_ok) / nh, 1)}\\%)"],
            ["Số ngày trong chuỗi", vn(nd, 0)],
            [r"Số ngày hợp lệ ($\geq 20$ giờ có số liệu) (tỉ lệ)", f"{vn(nd_ok, 0)} ({vn(100 * nd_ok / nd, 1)}\\%)"],
            ["Số bản ghi trùng (ngày, giờ)", vn(N["qc"]["n_dup"], 0)],
            ["Thời kỳ thiếu số liệu chính", runs_txt],
            ["Ngày thiếu lẻ tẻ", f"{N['missing']['n_invalid_day1']} ngày mùng 1 hằng tháng"],
            [r"Số tháng hợp lệ ($\geq 90\%$ ngày hợp lệ)", f"{n_mon_ok}/120"],
            ["Số năm đủ 12 tháng hợp lệ", f"{int(year_ok.sum())}/10"],
            ["Độ phân giải", "0,1 mm"],
        ],
    )

    # --- Mưa giờ
    hv = hourly.dropna(subset=["rain_mm"])
    hs = {
        "all": rain_stats(hv["rain_mm"], (20, 50)),
        "mua": rain_stats(hv.loc[hv["season"] == "mua", "rain_mm"], (20, 50)),
        "kho": rain_stats(hv.loc[hv["season"] == "kho", "rain_mm"], (20, 50)),
    }
    N["hourly_stats"] = hs
    write_rows("gio", stat_rows(hs, unit="giờ", big=(20, 50)))

    # top giờ
    top_h = hv.nlargest(5, "rain_mm")
    N["top_hours"] = [
        {"date": vn_date(r.date), "hour": int(r.hour), "rain": float(r.rain_mm)} for r in top_h.itertuples()
    ]
    # chu trình ngày
    diurnal = hv.groupby(["season", "hour"])["rain_mm"].mean().unstack(0)
    wetfreq = hv.assign(w=hv["rain_mm"] >= WET).groupby(["season", "hour"])["w"].mean().unstack(0) * 100
    N["diurnal"] = {
        "peak_hour_mua": int(diurnal["mua"].idxmax()),
        "peak_val_mua": float(diurnal["mua"].max()),
        "min_hour_mua": int(diurnal["mua"].idxmin()),
        "min_val_mua": float(diurnal["mua"].min()),
        "peak_hour_kho": int(diurnal["kho"].idxmax()),
        "peak_val_kho": float(diurnal["kho"].max()),
        "min_hour_kho": int(diurnal["kho"].idxmin()),
        "min_val_kho": float(diurnal["kho"].min()),
    }

    # --- Mưa ngày
    dv = daily[daily["valid"]]
    ds = {
        "all": rain_stats(dv["rain_mm"], (50, 100)),
        "mua": rain_stats(dv.loc[dv["season"] == "mua", "rain_mm"], (50, 100)),
        "kho": rain_stats(dv.loc[dv["season"] == "kho", "rain_mm"], (50, 100)),
    }
    N["daily_stats"] = ds
    write_rows("ngay", stat_rows(ds, unit="ngày", big=(50, 100), daily=True))
    top_d = dv.nlargest(5, "rain_mm")
    N["top_days"] = [{"date": vn_date(r.date), "rain": float(r.rain_mm)} for r in top_d.itertuples()]
    N["share_days_gt100_rain"] = float(
        100 * dv.loc[dv["rain_mm"] > 100, "rain_mm"].sum() / dv["rain_mm"].sum()
    )

    # --- Mưa tháng
    mv = mon[mon["valid"]]
    rows = []
    mstat = {}
    for m in range(1, 13):
        x = mv.loc[mv["month"] == m, "rain"]
        s = basic_stats(x)
        mstat[m] = s
        rows.append([m, s["n"], vn(s["mean"]), vn(s["std"]), vn(s["min"]), vn(s["median"]), vn(s["max"])])
    write_rows("thang", rows)
    N["monthly"] = {
        str(m): {k: float(v) for k, v in s.items()} for m, s in mstat.items()
    }
    max_month = mv.loc[mv["rain"].idxmax()]
    N["monthly_max"] = {
        "month": int(max_month.month),
        "year": int(max_month.year),
        "rain": float(max_month.rain),
    }
    clim = {m: mstat[m]["mean"] for m in mstat}
    N["rainy_months_share_clim"] = float(100 * sum(clim[m] for m in RAINY) / sum(clim.values()))
    ms = basic_stats(mv["rain"])
    N["monthly_all"] = ms
    write_rows(
        "thang_chung",
        [
            ["Số tháng hợp lệ", ms["n"]],
            ["Trung bình (mm)", vn(ms["mean"])],
            ["Độ lệch chuẩn (mm)", vn(ms["std"])],
            ["CV (\\%)", vn(ms["cv"])],
            ["Trung vị (mm)", vn(ms["median"])],
            ["Phân vị 25\\% (mm)", vn(ms["p25"])],
            ["Phân vị 75\\% (mm)", vn(ms["p75"])],
            ["Phân vị 90\\% (mm)", vn(ms["p90"])],
            ["Phân vị 95\\% (mm)", vn(ms["p95"])],
            ["Nhỏ nhất (mm)", vn(ms["min"])],
            ["Lớn nhất (mm)", vn(ms["max"])],
            ["Độ lệch (skewness)", vn(ms["skew"], 2)],
        ],
    )

    # --- Năm và mùa
    yrows = []
    ann = []
    for y in YEARS:
        my = mon[mon["year"] == y]
        ok_year = bool(my["valid"].all())
        ok_mua = bool(my[my["month"].isin(RAINY)]["valid"].all())
        ok_kho = bool(my[my["month"].isin(DRY)]["valid"].all())
        tot = my["rain"].sum()
        mua = my.loc[my["month"].isin(RAINY), "rain"].sum()
        kho = my.loc[my["month"].isin(DRY), "rain"].sum()
        nwet = int(my["n_wet"].sum())
        ann.append(
            dict(year=y, tot=tot, mua=mua, kho=kho, nwet=nwet, ok_year=ok_year, ok_mua=ok_mua, ok_kho=ok_kho)
        )
        star = lambda ok: "" if ok else "$^{*}$"
        yrows.append(
            [
                y,
                vn(tot) + star(ok_year),
                vn(mua) + star(ok_mua),
                vn(kho) + star(ok_kho),
                vn(100 * mua / tot) + star(ok_year),
                str(nwet) + star(ok_year),
            ]
        )
    write_rows("nam", yrows)
    ann = pd.DataFrame(ann)
    N["annual"] = ann.to_dict(orient="records")

    sa = basic_stats(ann.loc[ann.ok_year, "tot"])
    sm = basic_stats(ann.loc[ann.ok_mua, "mua"])
    sk = basic_stats(ann.loc[ann.ok_kho, "kho"])
    sn = basic_stats(ann.loc[ann.ok_year, "nwet"])
    share = 100 * ann.loc[ann.ok_year, "mua"] / ann.loc[ann.ok_year, "tot"]
    ss = basic_stats(share)
    N["annual_stats"] = {"tot": sa, "mua": sm, "kho": sk, "nwet": sn, "share": ss}
    valid_ann = ann[ann.ok_year]
    N["annual_extremes"] = {
        "wettest": int(valid_ann.loc[valid_ann.tot.idxmax(), "year"]),
        "wettest_mm": float(valid_ann.tot.max()),
        "driest": int(valid_ann.loc[valid_ann.tot.idxmin(), "year"]),
        "driest_mm": float(valid_ann.tot.min()),
        "mua_max_year": int(ann.loc[ann.ok_mua].sort_values("mua").iloc[-1].year),
        "mua_max": float(ann.loc[ann.ok_mua, "mua"].max()),
        "mua_min_year": int(ann.loc[ann.ok_mua].sort_values("mua").iloc[0].year),
        "mua_min": float(ann.loc[ann.ok_mua, "mua"].min()),
        "y2017_tot_incomplete": float(ann.loc[ann.year == 2017, "tot"].iloc[0]),
        "y2017_mua": float(ann.loc[ann.year == 2017, "mua"].iloc[0]),
    }

    def srow(label, s, nd=1):
        return [label, s["n"], vn(s["mean"], nd), vn(s["std"], nd), vn(s["cv"]), vn(s["min"], nd),
                vn(s["median"], nd), vn(s["max"], nd), vn(s["skew"], 2)]

    write_rows(
        "nam_thongke",
        [
            srow("Mưa năm (mm)", sa),
            srow("Mùa mưa IX--XII (mm)", sm),
            srow("Mùa khô I--VIII (mm)", sk),
            srow("Tỉ lệ mùa mưa (\\%)", ss),
            srow("Số ngày mưa", sn),
        ],
    )

    # --- Hình
    fig_qc(daily, mon)
    fig_daily_dist(dv, ds)
    fig_hourly_dist(hv, diurnal)
    fig_monthly(mv)
    fig_annual(ann)
    return ann


def stat_rows(s: dict, unit: str, big: tuple, daily: bool = False) -> list:
    c = ["all", "mua", "kho"]
    rows = [
        [f"Số {unit} có số liệu" if unit == "giờ" else "Số ngày hợp lệ"] + [vn(s[k]["n"], 0) for k in c],
        ["Trung bình (mm)"] + [vn(s[k]["mean"], 2) for k in c],
        ["Độ lệch chuẩn (mm)"] + [vn(s[k]["std"], 2) for k in c],
        ["CV (\\%)"] + [vn(s[k]["cv"], 1) for k in c],
        ["Trung vị (mm)"] + [vn(s[k]["median"], 1) for k in c],
        ["Phân vị 75\\% (mm)"] + [vn(s[k]["p75"], 1) for k in c],
        ["Phân vị 90\\% (mm)"] + [vn(s[k]["p90"], 1) for k in c],
        ["Phân vị 95\\% (mm)"] + [vn(s[k]["p95"], 1) for k in c],
        ["Phân vị 99\\% (mm)"] + [vn(s[k]["p99"], 1) for k in c],
        ["Lớn nhất (mm)"] + [vn(s[k]["max"], 1) for k in c],
        ["Độ lệch (skewness)"] + [vn(s[k]["skew"], 2) for k in c],
        [f"Số {unit} mưa $\\geq 1$ mm"] + [vn(s[k]["n_wet"], 0) for k in c],
        [f"Tần suất {unit} mưa (\\%)"] + [vn(s[k]["freq_wet"], 1) for k in c],
        [f"Mưa TB {unit} mưa (mm)"] + [vn(s[k]["mean_wet"], 2) for k in c],
        [f"Trung vị {unit} mưa (mm)"] + [vn(s[k]["median_wet"], 1) for k in c],
        [f"Số {unit} mưa $> {big[0]}$ mm"] + [vn(s[k]["n_big1"], 0) for k in c],
        [f"Số {unit} mưa $> {big[1]}$ mm"] + [vn(s[k]["n_big2"], 0) for k in c],
    ]
    return rows


def fig_qc(daily, mon):
    mat = mon.pivot(index="year", columns="month", values="frac") * 100
    fig, ax = plt.subplots(figsize=(8, 4.2))
    im = ax.imshow(mat.values, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(12), [str(m) for m in range(1, 13)])
    ax.set_yticks(range(len(mat.index)), [str(y) for y in mat.index])
    ax.set_xlabel("Tháng")
    ax.set_ylabel("Năm")
    ax.grid(False)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > 60 else C_ORANGE, fontweight="bold" if v < 90 else "normal")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Tỉ lệ ngày hợp lệ (%)")
    ax.set_title("Tỉ lệ ngày có số liệu hợp lệ theo tháng — trạm Trà My 2008–2017")
    save("fig01_qc_heatmap.png")


def fig_daily_dist(dv, ds):
    x = dv["rain_mm"].dropna()
    wet = x[x >= WET]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    ax = axes[0]
    ax.hist(wet, bins=np.arange(0, wet.max() + 20, 20), color=C_RAIN, edgecolor="white")
    ax.set_yscale("log")
    ax.set_xlabel("Lượng mưa ngày (mm)")
    ax.set_ylabel("Số ngày (thang log)")
    ax.set_title("(a) Tần suất lượng mưa ngày mưa (≥ 1 mm)")
    ax = axes[1]
    xs = np.sort(x.values)
    ax.plot(xs, np.arange(1, len(xs) + 1) / len(xs) * 100, color=C_SEA, lw=1.8)
    ax.set_xscale("symlog", linthresh=1)
    for key, col, lab in [("p90", C_GOLD, "P90"), ("p95", C_ORANGE, "P95"), ("p99", "#7a1f1f", "P99")]:
        v = ds["all"][key]
        ax.axvline(v, color=col, ls="--", lw=1.3, label=f"{lab} = {fv(v)} mm")
    ax.legend(loc="lower right")
    ax.set_xlabel("Lượng mưa ngày (mm, thang symlog)")
    ax.set_ylabel("Tần suất tích lũy (%)")
    ax.set_title("(b) Phân bố tích lũy và phân vị (mọi ngày hợp lệ)")
    save("fig02_daily_dist.png")


def fig_hourly_dist(hv, diurnal):
    wet = hv.loc[hv["rain_mm"] >= WET, "rain_mm"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    ax = axes[0]
    ax.hist(wet, bins=np.arange(0, wet.max() + 3, 3), color=C_RAIN, edgecolor="white")
    ax.set_yscale("log")
    ax.set_xlabel("Lượng mưa giờ (mm)")
    ax.set_ylabel("Số giờ (thang log)")
    ax.set_title("(a) Tần suất lượng mưa giờ mưa (≥ 1 mm)")
    ax = axes[1]
    hrs = diurnal.index.values
    ax.plot(hrs, diurnal["mua"].values, "-o", ms=3.5, color=C_ORANGE, label="Mùa mưa (IX–XII)")
    ax.plot(hrs, diurnal["kho"].values, "-s", ms=3.5, color=C_SEA, label="Mùa khô (I–VIII)")
    ax.set_xticks(range(1, 25, 2))
    ax.set_xlabel("Giờ trong ngày")
    ax.set_ylabel("Lượng mưa giờ trung bình (mm)")
    ax.set_title("(b) Chu trình ngày của lượng mưa giờ")
    ax.legend()
    save("fig03_hourly_dist.png")


def fig_monthly(mv):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.hist(mv["rain"], bins=np.arange(0, mv["rain"].max() + 100, 100), color=C_RAIN, edgecolor="white")
    ax.axvline(mv["rain"].mean(), color=C_ORANGE, ls="--", lw=1.4, label=f"Trung bình = {fv(mv['rain'].mean())} mm")
    ax.axvline(mv["rain"].median(), color=C_SEA, ls=":", lw=1.6, label=f"Trung vị = {fv(mv['rain'].median())} mm")
    ax.set_xlabel("Tổng lượng mưa tháng (mm)")
    ax.set_ylabel("Số tháng")
    ax.set_title("Phân bố tần suất tổng lượng mưa tháng (tháng hợp lệ)")
    ax.legend()
    save("fig04_monthly_hist.png")

    data = [mv.loc[mv["month"] == m, "rain"].values for m in range(1, 13)]
    fig, ax = plt.subplots(figsize=(8, 4.3))
    bp = ax.boxplot(data, patch_artist=True, widths=0.6, showmeans=True,
                    meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor=C_DARK, ms=4),
                    medianprops=dict(color=C_DARK))
    for m, box in enumerate(bp["boxes"], start=1):
        box.set_facecolor(C_ORANGE if m in RAINY else C_SOFT)
        box.set_alpha(0.85)
    ax.set_xticks(range(1, 13), ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"])
    ax.set_xlabel("Tháng")
    ax.set_ylabel("Tổng lượng mưa tháng (mm)")
    ax.set_title("Biểu đồ hộp tổng lượng mưa theo tháng (cam: mùa mưa IX–XII, ◇: trung bình)")
    save("fig05_monthly_box.png")


def fig_annual(ann):
    fig, (ax, axb) = plt.subplots(2, 1, figsize=(8.5, 5.6), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1.2]})
    x = np.arange(len(ann))
    alpha = np.where(ann["ok_year"], 1.0, 0.45)
    for i, r in ann.iterrows():
        ax.bar(i, r["kho"], color=C_SOFT, alpha=alpha[i], edgecolor="white",
               hatch="" if r["ok_kho"] else "//", label="Mùa khô (I–VIII)" if i == 0 else None)
        ax.bar(i, r["mua"], bottom=r["kho"], color=C_ORANGE, alpha=alpha[i], edgecolor="white",
               hatch="" if r["ok_mua"] else "//", label="Mùa mưa (IX–XII)" if i == 0 else None)
        ax.text(i, r["tot"] - 80, f"{r['tot']:.0f}", ha="center", va="top", fontsize=8,
                color="white", fontweight="bold")
    ax.set_ylabel("Lượng mưa (mm)")
    ax.set_ylim(0, ann["tot"].max() * 1.12)
    ax.legend(loc="upper left", ncol=2)
    ax.set_title("(a) Tổng lượng mưa năm theo mùa — trạm Trà My")
    axb.plot(x, ann["nwet"], "-o", color=C_DARK, ms=4)
    for i, v in enumerate(ann["nwet"]):
        axb.text(i, v + 6, str(v), ha="center", fontsize=8)
    axb.set_ylim(ann["nwet"].min() * 0.8, ann["nwet"].max() * 1.15)
    axb.set_ylabel("Số ngày mưa")
    axb.set_title("(b) Số ngày mưa ≥ 1 mm", fontsize=10)
    axb.set_xticks(x, [str(y) + ("" if ok else "*") for y, ok in zip(ann["year"], ann["ok_year"])])
    axb.set_xlabel("Năm (* năm có tháng thiếu số liệu)")
    save("fig06_annual_season.png")


# ---------------------------------------------------------------------------
# Phase 2 — Câu 2
# ---------------------------------------------------------------------------
def q2(hourly, daily):
    rx = compute_rx(daily)
    hv = hourly.dropna(subset=["rain_mm"])
    idx = hv.groupby("year")["rain_mm"].idxmax()
    ams_h = hv.loc[idx, ["year", "date", "hour", "rain_mm", "landslide"]].rename(columns={"rain_mm": "rx1h"})
    rx = rx.merge(ams_h, on="year")
    valid_pct = daily.groupby("year")["valid"].mean() * 100
    slide_days = set(daily.loc[daily["landslide"] == 1, "date"])
    rx["valid_pct"] = rx["year"].map(valid_pct)
    rx["d1"] = pd.to_datetime(rx["RX1day_date"])
    rx["d5s"] = pd.to_datetime(rx["RX5day_start"])
    rx["d5e"] = pd.to_datetime(rx["RX5day_end"])
    rx["slide1"] = rx["d1"].isin(slide_days)
    rx["slide5"] = [
        any(pd.Timestamp(d) in slide_days for d in pd.date_range(a, b)) for a, b in zip(rx["d5s"], rx["d5e"])
    ]
    rx["ratio"] = rx["RX5day_mm"] / rx["RX1day_mm"]

    rows = []
    for r in rx.itertuples():
        dag = r"$^{\dagger}$" if r.slide1 else ""
        dag5 = r"$^{\dagger}$" if r.slide5 else ""
        rows.append([r.year, vn(r.valid_pct, 1), vn(r.RX1day_mm), vn_date(r.d1) + dag, vn(r.RX5day_mm),
                     f"{vn_dm(r.d5s)}--{vn_dm(r.d5e)}" + dag5, vn(r.rx1h)])
    write_rows("rx", rows)

    def srow(label, x, nd=1):
        s = basic_stats(x)
        return [label, s["n"], vn(s["mean"], nd), vn(s["std"], nd), vn(s["cv"]), vn(s["min"], nd),
                vn(s["median"], nd), vn(s["max"], nd)], s

    r1, s1 = srow("Rx1day (mm)", rx["RX1day_mm"])
    r5, s5 = srow("Rx5day (mm)", rx["RX5day_mm"])
    rh, sh = srow("Rx1hour (mm)", rx["rx1h"])
    rr, sr = srow("Rx5day/Rx1day", rx["ratio"], nd=2)
    write_rows("rx_thongke", [r1, r5, rh, rr])

    months1 = rx["d1"].dt.month.value_counts().sort_index()
    monthsh = pd.to_datetime(rx["date"]).dt.month.value_counts().sort_index()
    share_day_in_5 = rx["RX1day_mm"] / rx["RX5day_mm"] * 100
    N["rx"] = {
        "rows": [
            {
                "year": int(r.year), "rx1": float(r.RX1day_mm), "d1": vn_date(r.d1), "rx5": float(r.RX5day_mm),
                "d5": f"{vn_date(r.d5s)}--{vn_date(r.d5e)}", "rx1h": float(r.rx1h),
                "h_date": vn_date(r.date), "h_hour": int(r.hour), "slide1": bool(r.slide1), "slide5": bool(r.slide5),
                "valid_pct": float(r.valid_pct), "ratio": float(r.ratio),
            }
            for r in rx.itertuples()
        ],
        "stats_rx1": s1, "stats_rx5": s5, "stats_rx1h": sh, "stats_ratio": sr,
        "months_rx1": {int(k): int(v) for k, v in months1.items()},
        "months_rx1h": {int(k): int(v) for k, v in monthsh.items()},
        "n_slide1": int(rx["slide1"].sum()),
        "n_slide5": int(rx["slide5"].sum()),
        "rx1_in_rainy": int(rx["d1"].dt.month.isin(RAINY).sum()),
        "rx1h_in_rainy": int(pd.to_datetime(rx["date"]).dt.month.isin(RAINY).sum()),
        "max_share_day_in_5": float(share_day_in_5.max()),
        "mean_share_day_in_5": float(share_day_in_5.mean()),
    }
    # đợt lớn nhất
    imax = rx["RX5day_mm"].idxmax()
    ev = rx.loc[imax]
    fig_rx(rx)
    fig_rx_hist(rx)
    fig_event(hourly, ev)
    return rx


def fig_rx(rx):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    x = np.arange(len(rx))
    w = 0.38
    ax.bar(x - w / 2, rx["RX1day_mm"], w, color=C_SEA, label="Rx1day")
    ax.bar(x + w / 2, rx["RX5day_mm"], w, color=C_ORANGE, label="Rx5day")
    for i, r in rx.iterrows():
        ax.text(i - w / 2, r["RX1day_mm"] + 15, f"{r['RX1day_mm']:.0f}\n{r['d1']:%d/%m}", ha="center", fontsize=6.5)
        ax.text(i + w / 2, r["RX5day_mm"] + 15, f"{r['RX5day_mm']:.0f}", ha="center", fontsize=6.5)
        if r["slide1"]:
            ax.plot(i - w / 2, r["RX1day_mm"] + 115, marker="v", color="#7a1f1f", ms=6)
    ax.plot([], [], marker="v", color="#7a1f1f", ls="", label="Ngày Rx1day có trượt lở")
    ax.set_xticks(x, rx["year"].astype(str))
    ax.set_ylabel("Lượng mưa (mm)")
    ax.set_xlabel("Năm")
    ax.set_ylim(0, rx["RX5day_mm"].max() * 1.15)
    ax.legend(loc="upper left")
    ax.set_title("Rx1day và Rx5day theo năm — trạm Trà My (nhãn: giá trị và ngày xảy ra Rx1day)")
    save("fig07_rx_by_year.png")


def fig_rx_hist(rx):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, col, title in [(axes[0], "RX1day_mm", "(a) Rx1day"), (axes[1], "RX5day_mm", "(b) Rx5day")]:
        x = rx[col].values
        ax.hist(x, bins=6, density=True, color=C_SOFT, edgecolor="white", label="Tần suất (mật độ)")
        grid = np.linspace(0, x.max() * 1.5, 300)
        g = stats.gumbel_r.fit(x)
        ln = stats.lognorm.fit(x, floc=0)
        ax.plot(grid, stats.gumbel_r.pdf(grid, *g), color=C_SEA, lw=2, label="Gumbel")
        ax.plot(grid, stats.lognorm.pdf(grid, *ln), color=C_ORANGE, lw=2, ls="--", label="Chuẩn loga")
        ax.plot(x, np.zeros_like(x), "|", color=C_DARK, ms=14)
        ax.set_xlabel("Lượng mưa (mm)")
        ax.set_ylabel("Mật độ xác suất")
        ax.set_title(title + " (n = 10 năm)")
        ax.legend()
    save("fig08_rx_hist_fit.png")


def fig_event(hourly, ev):
    a = pd.Timestamp(ev["d5s"]) - pd.Timedelta(days=1)
    b = pd.Timestamp(ev["d5e"]) + pd.Timedelta(days=1)
    h = hourly[(hourly["date"] >= a) & (hourly["date"] <= b)].copy()
    h["t"] = h["date"] + pd.to_timedelta(h["hour"], unit="h")
    h["r"] = h["rain_mm"].fillna(0)
    in5 = (h["date"] >= ev["d5s"]) & (h["date"] <= ev["d5e"])
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(h["t"], h["r"], width=1 / 24, color=np.where(in5, C_RAIN, C_SOFT), align="edge")
    for t in h.loc[h["landslide"] == 1, "t"]:
        ax.axvspan(t - pd.Timedelta(hours=1), t, color="#7a1f1f", alpha=0.15, lw=0)
    ax.set_ylabel("Lượng mưa giờ (mm)")
    ax.set_xlabel("Thời gian")
    ax2 = ax.twinx()
    cum = h.loc[in5, "r"].cumsum()
    ax2.plot(h.loc[in5, "t"], cum, color=C_ORANGE, lw=2, label="Lượng mưa tích lũy trong 5 ngày")
    ax2.set_ylabel("Lượng mưa tích lũy (mm)")
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax2.plot([], [], color="#7a1f1f", alpha=0.3, lw=8, label="Giờ có ghi nhận trượt lở")
    ax2.legend(loc="upper left")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
    ax.set_title(
        f"Đợt mưa Rx5day lớn nhất: {pd.Timestamp(ev['d5s']):%d/%m}–{pd.Timestamp(ev['d5e']):%d/%m/%Y} "
        f"({fv(ev['RX5day_mm'])} mm)"
    )
    N["event"] = {
        "start": vn_date(ev["d5s"]), "end": vn_date(ev["d5e"]), "total": float(ev["RX5day_mm"]),
        "max_hour": float(h.loc[in5, "r"].max()),
        "max_hour_time": f"{vn_date(h.loc[h.loc[in5, 'r'].idxmax(), 'date'])} giờ {int(h.loc[h.loc[in5, 'r'].idxmax(), 'hour'])}",
        "hours_ge10": int((h.loc[in5, "r"] >= 10).sum()),
        "landslide_hours": int(h.loc[in5, "landslide"].sum()),
        "daily": {vn_date(d): float(v) for d, v in h.loc[in5].groupby("date")["r"].sum().items()},
    }
    save("fig09_event_max.png")


# ---------------------------------------------------------------------------
# Phase 3 — Câu 3
# ---------------------------------------------------------------------------
def thr_block(values: pd.Series, n_years: float) -> dict:
    v = values[values >= WET]
    r95 = float(np.percentile(v, 95))
    r99 = float(np.percentile(v, 99))
    return {
        "n_wet": int(len(v)), "R95p": r95, "R99p": r99,
        "n95": int((v > r95).sum()), "n99": int((v > r99).sum()),
        "per_year95": (v > r95).sum() / n_years, "per_year99": (v > r99).sum() / n_years,
        "share95": 100 * v[v > r95].sum() / v.sum(), "share99": 100 * v[v > r99].sum() / v.sum(),
    }


def q3(hourly, daily):
    hv = hourly.dropna(subset=["rain_mm"])
    dv = daily[daily["valid"]]
    T = {
        "h_all": thr_block(hv["rain_mm"], 10),
        "h_mua": thr_block(hv.loc[hv["season"] == "mua", "rain_mm"], 10),
        "d_all": thr_block(dv["rain_mm"], 10),
        "d_mua": thr_block(dv.loc[dv["season"] == "mua", "rain_mm"], 10),
    }
    N["thr"] = T
    keys = ["h_all", "h_mua", "d_all", "d_mua"]
    write_rows(
        "nguong",
        [
            ["Số giờ / ngày mưa $\\geq 1$ mm"] + [vn(T[k]["n_wet"], 0) for k in keys],
            ["R95p (mm)"] + [vn(T[k]["R95p"], 1) for k in keys],
            ["R99p (mm)"] + [vn(T[k]["R99p"], 1) for k in keys],
            ["Số lần vượt R95p"] + [vn(T[k]["n95"], 0) for k in keys],
            ["Số lần vượt R99p"] + [vn(T[k]["n99"], 0) for k in keys],
            ["Số lần vượt R95p TB/năm"] + [vn(T[k]["per_year95"], 1) for k in keys],
            ["Số lần vượt R99p TB/năm"] + [vn(T[k]["per_year99"], 1) for k in keys],
            ["Đóng góp của các lần $>$ R95p (\\%)"] + [vn(T[k]["share95"], 1) for k in keys],
            ["Đóng góp của các lần $>$ R99p (\\%)"] + [vn(T[k]["share99"], 1) for k in keys],
        ],
    )
    h95, h99 = T["h_all"]["R95p"], T["h_all"]["R99p"]
    d95, d99 = T["d_all"]["R95p"], T["d_all"]["R99p"]
    ey = []
    for y in YEARS:
        hy = hv.loc[hv["year"] == y, "rain_mm"]
        dy = dv.loc[dv["year"] == y, "rain_mm"]
        ey.append(dict(year=y, h95=int((hy > h95).sum()), h99=int((hy > h99).sum()),
                       d95=int((dy > d95).sum()), d99=int((dy > d99).sum())))
    ey = pd.DataFrame(ey)
    write_rows("vuot_nguong", [[r.year, r.h95, r.h99, r.d95, r.d99] for r in ey.itertuples()])
    N["exceed_year"] = ey.to_dict(orient="records")
    N["exceed_month_day95"] = {int(k): int(v) for k, v in dv.loc[dv["rain_mm"] > d95, "month"].value_counts().sort_index().items()}
    N["exceed_month_hour95"] = {int(k): int(v) for k, v in hv.loc[hv["rain_mm"] > h95, "month"].value_counts().sort_index().items()}
    N["n_days_gt_d99_with_slide"] = int(((dv["rain_mm"] > d99) & (dv["landslide"] == 1)).sum())
    N["n_slide_days"] = int((daily["landslide"] == 1).sum())
    slide = daily[daily["landslide"] == 1]
    N["slide_days_gt_d95"] = int((slide["rain_mm"] > d95).sum())

    # Hình ngưỡng
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, v, r95, r99, step, lab, title in [
        (axes[0], hv["rain_mm"], h95, h99, 3, "Lượng mưa giờ (mm)", "(a) Mưa giờ ≥ 1 mm"),
        (axes[1], dv["rain_mm"], d95, d99, 20, "Lượng mưa ngày (mm)", "(b) Mưa ngày ≥ 1 mm"),
    ]:
        w = v[v >= WET]
        ax.hist(w, bins=np.arange(0, w.max() + step, step), color=C_SOFT, edgecolor="white")
        ax.set_yscale("log")
        ax.axvline(r95, color=C_GOLD, lw=2, label=f"R95p = {fv(r95)} mm")
        ax.axvline(r99, color=C_ORANGE, lw=2, label=f"R99p = {fv(r99)} mm")
        ax.set_xlabel(lab)
        ax.set_ylabel("Tần suất (thang log)")
        ax.set_title(title)
        ax.legend()
    save("fig10_thresholds.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = np.arange(len(ey))
    for ax, a, b, title in [
        (axes[0], "h95", "h99", "(a) Số giờ mưa vượt ngưỡng"),
        (axes[1], "d95", "d99", "(b) Số ngày mưa vượt ngưỡng"),
    ]:
        ax.bar(x - 0.2, ey[a], 0.4, color=C_GOLD, label="> R95p")
        ax.bar(x + 0.2, ey[b], 0.4, color=C_ORANGE, label="> R99p")
        for i in x:
            ax.text(i - 0.2, ey[a][i] + 0.3, str(ey[a][i]), ha="center", fontsize=7)
            ax.text(i + 0.2, ey[b][i] + 0.3, str(ey[b][i]), ha="center", fontsize=7)
        ax.set_xticks(x, ey["year"].astype(str), rotation=45)
        ax.set_ylabel("Số lần")
        ax.set_title(title)
        ax.legend()
    save("fig11_exceed_year.png")
    return T


# ---------------------------------------------------------------------------
# Phase 4 — Câu 4
# ---------------------------------------------------------------------------
DISTS = {
    "Gumbel": (stats.gumbel_r, {}, 2),
    "GEV": (stats.genextreme, {}, 3),
    "Chuẩn loga": (stats.lognorm, {"floc": 0}, 2),
    "Gamma": (stats.gamma, {"floc": 0}, 2),
    "Weibull": (stats.weibull_min, {"floc": 0}, 2),
}


def fit_dist(name: str, x: np.ndarray):
    dist, kw, _ = DISTS[name]
    if name == "GEV":
        c0, loc0, sc0, _ = gev_from_lmoments(x)
        cands = []
        for args in [((c0,), dict(loc=loc0, scale=sc0)), ((), {})]:
            try:
                p = dist.fit(x, *args[0], **args[1])
                ll = dist.logpdf(x, *p).sum()
                if np.isfinite(ll) and abs(p[0]) < 1:
                    cands.append((ll, p))
            except Exception:
                pass
        return max(cands, key=lambda t: t[0])[1]
    return dist.fit(x, **kw)


def ad_stat(x, cdf) -> float:
    x = np.sort(x)
    n = len(x)
    F = np.clip(cdf(x), 1e-12, 1 - 1e-12)
    i = np.arange(1, n + 1)
    return float(-n - np.mean((2 * i - 1) * (np.log(F) + np.log(1 - F[::-1]))))


def param_text(name, p) -> str:
    if name == "Gumbel":
        return f"$\\mu$\\,=\\,{vn(p[0], 2)}; $\\beta$\\,=\\,{vn(p[1], 2)}"
    if name == "GEV":
        return f"$\\xi$\\,=\\,{vn(-p[0], 3)}; $\\mu$\\,=\\,{vn(p[1], 2)}; $\\sigma$\\,=\\,{vn(p[2], 2)}"
    if name == "Chuẩn loga":
        return f"$\\mu_{{\\ln}}$\\,=\\,{vn(np.log(p[2]), 3)}; $\\sigma_{{\\ln}}$\\,=\\,{vn(p[0], 3)}"
    if name == "Gamma":
        return f"$\\alpha$\\,=\\,{vn(p[0], 3)}; $\\theta$\\,=\\,{vn(p[2], 2)}"
    if name == "Weibull":
        return f"$k$\\,=\\,{vn(p[0], 3)}; $\\lambda$\\,=\\,{vn(p[2], 2)}"
    return ""


def fit_all(x: np.ndarray) -> dict:
    n = len(x)
    out = {}
    for name, (dist, _, k) in DISTS.items():
        p = fit_dist(name, x)
        ll = float(dist.logpdf(x, *p).sum())
        cdf = lambda v, d=dist, p=p: d.cdf(v, *p)
        out[name] = {
            "params": [float(v) for v in p],
            "logL": ll,
            "AIC": 2 * k - 2 * ll,
            "BIC": k * np.log(n) - 2 * ll,
            "KS": float(stats.kstest(x, cdf).statistic),
            "KS_p": float(stats.kstest(x, cdf).pvalue),
            "CvM": float(stats.cramervonmises(x, cdf).statistic),
            "AD": ad_stat(x, cdf),
            "rl": {T: float(dist.ppf(1 - 1 / T, *p)) for T in TS},
        }
    return out


def choose(fits: dict) -> str:
    two = {k: v for k, v in fits.items() if k != "GEV"}
    best = min(two, key=lambda k: two[k]["AIC"])
    if two["Gumbel"]["AIC"] - two[best]["AIC"] < 2:
        return "Gumbel"
    return best


def bootstrap(name: str, x: np.ndarray, params, T_grid) -> np.ndarray:
    dist = DISTS[name][0]
    n = len(x)
    out = []
    for _ in range(N_BOOT):
        xb = dist.rvs(*params, size=n, random_state=RNG)
        try:
            pb = fit_dist(name, xb)
            out.append(dist.ppf(1 - 1 / np.asarray(T_grid), *pb))
        except Exception:
            continue
    return np.array(out)


def decluster(t: np.ndarray, v: np.ndarray, u: float, gap: float) -> np.ndarray:
    m = v > u
    t, v = t[m], v[m]
    peaks = []
    cur = []
    last = None
    for ti, vi in zip(t, v):
        if last is not None and ti - last > gap:
            peaks.append(max(cur))
            cur = []
        cur.append(vi)
        last = ti
    if cur:
        peaks.append(max(cur))
    return np.array(peaks)


def gpd_rl(u, c, sc, lam, T):
    T = np.asarray(T, dtype=float)
    if abs(c) < 1e-6:
        return u + sc * np.log(lam * T)
    return u + sc / c * ((lam * T) ** c - 1)


def pot(t, v, u, gap, n_years) -> dict:
    peaks = decluster(t, v, u, gap)
    y = peaks - u
    c, _, sc = stats.genpareto.fit(y, floc=0)
    lam = len(peaks) / n_years
    boots = []
    for _ in range(N_BOOT):
        yb = RNG.choice(y, size=len(y), replace=True)
        cb, _, sb = stats.genpareto.fit(yb, floc=0)
        boots.append(gpd_rl(u, cb, sb, lam, TS))
    boots = np.array(boots)
    return {
        "u": u, "n_peaks": int(len(peaks)), "lam": lam, "xi": float(c), "sigma": float(sc),
        "rl": {T: float(gpd_rl(u, c, sc, lam, T)) for T in TS},
        "ci": {T: (float(np.percentile(boots[:, i], 2.5)), float(np.percentile(boots[:, i], 97.5)))
               for i, T in enumerate(TS)},
    }


def q4(hourly, daily, rx, thr):
    series = {
        "gio": (rx["rx1h"].values.astype(float), "Rx1hour"),
        "ngay": (rx["RX1day_mm"].values.astype(float), "Rx1day"),
    }
    T_grid = np.unique(np.concatenate([np.logspace(np.log10(1.05), np.log10(200), 60), TS]))
    res = {}
    for key, (x, label) in series.items():
        fits = fit_all(x)
        sel = choose(fits)
        boot = bootstrap(sel, x, fits[sel]["params"], T_grid)
        ci_grid = np.percentile(boot, [2.5, 97.5], axis=0)
        ci = {T: (float(ci_grid[0][np.argmin(abs(T_grid - T))]), float(ci_grid[1][np.argmin(abs(T_grid - T))]))
              for T in TS}
        mu_l, sg_l = gumbel_from_lmoments(x)
        lmom = {T: float(mu_l - sg_l * np.log(-np.log(1 - 1 / T))) for T in TS}
        imax = int(np.argmax(x))
        x_drop = np.delete(x, imax)
        pg = stats.gumbel_r.fit(x_drop)
        drop = {T: float(stats.gumbel_r.ppf(1 - 1 / T, *pg)) for T in TS}
        res[key] = dict(x=x, label=label, fits=fits, sel=sel, ci=ci, ci_grid=ci_grid, T_grid=T_grid,
                        lmom=lmom, lmom_params=(mu_l, sg_l), drop=drop, drop_val=float(x[imax]),
                        drop_year=int(rx["year"].iloc[imax]))

    # POT
    hv = hourly.dropna(subset=["rain_mm"]).sort_values("datetime")
    th = (hv["datetime"] - hv["datetime"].iloc[0]).dt.total_seconds().values / 3600
    res["gio"]["pot"] = pot(th, hv["rain_mm"].values, thr["h_all"]["R95p"], 24, len(hv) / 8766)
    dv = daily[daily["valid"]].sort_values("date")
    td = (dv["date"] - dv["date"].iloc[0]).dt.days.values.astype(float)
    res["ngay"]["pot"] = pot(td, dv["rain_mm"].values, thr["d_all"]["R95p"], 3, len(dv) / 365.25)

    # Bảng khớp phân bố
    for key in ("gio", "ngay"):
        r = res[key]
        rows = []
        for name, f in r["fits"].items():
            nm = name + ("$^{*}$" if name == r["sel"] else "")
            rows.append([nm, param_text(name, f["params"]), vn(f["logL"], 2), vn(f["AIC"], 2), vn(f["BIC"], 2),
                         vn(f["KS"], 3), vn(f["CvM"], 3), vn(f["AD"], 3)])
        write_rows(f"fit_{key}", rows)

    # Bảng chu kỳ
    rows = []
    for T in TS:
        cells = [f"{T} năm"]
        for key in ("gio", "ngay"):
            r = res[key]
            cells += [vn(r["fits"][r["sel"]]["rl"][T]), f"{vn(r['ci'][T][0])}--{vn(r['ci'][T][1])}"]
        rows.append(cells)
    write_rows("chuky", rows)

    # Bảng độ nhạy
    rows = []
    for key, label in (("gio", "Mưa giờ"), ("ngay", "Mưa ngày")):
        r = res[key]
        items = [(f"{n} (MLE)" + ("$^{*}$" if n == r["sel"] else ""), r["fits"][n]["rl"]) for n in DISTS]
        items.append(("Gumbel (L-moment)", r["lmom"]))
        items.append((f"POT--GPD (u = R95p = {vn(r['pot']['u'], 1)} mm)", r["pot"]["rl"]))
        items.append((f"Gumbel bỏ giá trị lớn nhất ({vn(r['drop_val'], 1)} mm, {r['drop_year']}; n = 9)", r["drop"]))
        for i, (nm, rl) in enumerate(items):
            first = f"\\multirow{{{len(items)}}}{{*}}{{{label}}}" if i == 0 else ""
            rule = r"\hline" if i == len(items) - 1 else r"\cline{2-6}"
            rows.append(([first, nm] + [vn(rl[T], 1) for T in TS], rule))
    write_rows("donhay", rows)

    # Số liệu cho nhận xét
    N["q4"] = {}
    for key in ("gio", "ngay"):
        r = res[key]
        allrl = {n: r["fits"][n]["rl"] for n in DISTS}
        allrl["L-moment"] = r["lmom"]
        allrl["POT"] = r["pot"]["rl"]
        allrl["drop"] = r["drop"]
        N["q4"][key] = {
            "sel": r["sel"],
            "fits": {n: {k: v for k, v in f.items() if k != "rl"} | {"rl": f["rl"]} for n, f in r["fits"].items()},
            "ci": r["ci"],
            "lmom": r["lmom"], "lmom_params": r["lmom_params"],
            "drop": r["drop"], "drop_val": r["drop_val"], "drop_year": r["drop_year"],
            "pot": r["pot"],
            "range_T100_models": [min(v[100] for v in allrl.values()), max(v[100] for v in allrl.values())],
            "range_T10_models": [min(v[10] for v in allrl.values()), max(v[10] for v in allrl.values())],
            "max_obs": float(r["x"].max()),
        }

    fig_freq(res["gio"], "fig12_freq_hourly.png", "Rx1hour — mưa giờ lớn nhất năm")
    fig_freq(res["ngay"], "fig13_freq_daily.png", "Rx1day — mưa ngày lớn nhất năm")
    fig_qq(res)
    return res


def fig_freq(r, fname, title):
    x = np.sort(r["x"])
    n = len(x)
    F = (np.arange(1, n + 1) - 0.44) / (n + 0.12)
    T_emp = 1 / (1 - F)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.fill_between(r["T_grid"], r["ci_grid"][0], r["ci_grid"][1], color=C_SOFT, alpha=0.45,
                    label=f"KTC 95% ({r['sel']}, bootstrap)")
    styles = {"Gumbel": ("-", C_SEA), "GEV": (":", "#555555"), "Chuẩn loga": ("--", C_ORANGE),
              "Gamma": ("-.", C_GOLD), "Weibull": ((0, (5, 1, 1, 1)), "#2f6f4e")}
    for name, f in r["fits"].items():
        ls, col = styles[name]
        y = DISTS[name][0].ppf(1 - 1 / r["T_grid"], *f["params"])
        ax.plot(r["T_grid"], y, ls=ls, color=col, lw=2.2 if name == r["sel"] else 1.3,
                label=name + (" (chọn)" if name == r["sel"] else ""))
    ax.plot(T_emp, x, "o", color=C_DARK, ms=6, label="Rx quan trắc (Gringorten)", zorder=5)
    sel = r["fits"][r["sel"]]
    for T in TS:
        ax.plot(T, sel["rl"][T], "s", color=C_ORANGE, ms=7, zorder=6)
        off, ha = ((-8, 12), "right") if T == 100 else ((6, -14), "left")
        ax.annotate(f"T={T}: {sel['rl'][T]:.0f} mm", (T, sel["rl"][T]), textcoords="offset points",
                    xytext=off, fontsize=8, ha=ha, color=C_ORANGE, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    ax.set_xscale("log")
    ax.set_xlim(1, 200)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200], ["1", "2", "5", "10", "20", "50", "100", "200"])
    ax.set_xlabel("Chu kỳ lặp lại T (năm, thang log)")
    ax.set_ylabel("Lượng mưa (mm)")
    ax.set_title(f"Đường tần suất {title}")
    ax.legend(fontsize=8, loc="upper left")
    save(fname)


def fig_qq(res):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, key, title in [(axes[0], "gio", "(a) Rx1hour"), (axes[1], "ngay", "(b) Rx1day")]:
        r = res[key]
        x = np.sort(r["x"])
        n = len(x)
        F = (np.arange(1, n + 1) - 0.44) / (n + 0.12)
        for name, col, mk in [(r["sel"], C_SEA, "o"), ("GEV", "#555555", "^")]:
            q = DISTS[name][0].ppf(F, *r["fits"][name]["params"])
            ax.plot(q, x, mk, color=col, ms=6, label=name)
        lim = [0, max(x.max(), q.max()) * 1.1]
        ax.plot(lim, lim, color=C_ORANGE, lw=1.2, ls="--", label="Đường 1:1")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_xlabel("Phân vị lý thuyết (mm)")
        ax.set_ylabel("Phân vị quan trắc (mm)")
        ax.set_title(f"{title} — biểu đồ Q–Q")
        ax.legend()
    save("fig14_qq.png")


# ---------------------------------------------------------------------------
def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 4)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return vn_date(o)
    return o


def main() -> None:
    setup_style()
    hourly, daily, mon = prepare()
    check_missing_pattern(hourly, daily)
    print("Câu 1 …")
    q1(hourly, daily, mon)
    print("Câu 2 …")
    rx = q2(hourly, daily)
    print("Câu 3 …")
    thr = q3(hourly, daily)
    print("Câu 4 …")
    q4(hourly, daily, rx, thr)
    NUM_PATH.parent.mkdir(parents=True, exist_ok=True)
    NUM_PATH.write_text(json.dumps(to_jsonable(N), ensure_ascii=False, indent=1), encoding="utf-8")
    print("Xong:", NUM_PATH)


if __name__ == "__main__":
    main()

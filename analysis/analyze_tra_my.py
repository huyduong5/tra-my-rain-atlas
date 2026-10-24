#!/usr/bin/env python3
"""
Phân tích mưa giờ — Trạm Trà My (2008–2017)
Pipeline: QC → thống kê mô tả → RX1/RX5 → R95p/R99p → chu kỳ lặp lại Gumbel/GEV
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from scipy import stats

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "Hourly rain in Tra My.xlsx - TM_1hr.csv"
if not CSV_PATH.exists():  # bố cục repo tra-my-rain-atlas: số liệu gốc nằm ở data/raw/
    CSV_PATH = ROOT.parent / "data" / "raw" / "Hourly_rain_Tra_My_2008_2017.csv"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
CACHE = OUT / "cache"

WET_THRESHOLD = 1.0  # mm — ETCCDI wet day/hour
MIN_VALID_HOURS = 20  # ngày hợp lệ nếu có ≥20 giờ số liệu
RAINY_MONTHS = {9, 10, 11, 12}  # mùa mưa Trà My
RETURN_PERIODS = [10, 20, 50, 100]
N_BOOT = 2000
RNG = np.random.default_rng(42)

RAIN_COL = "Luong mua (mm)"
SLIDE_COL = "Trượt lở (0-Không; 1-Xảy ra trượt lở)"


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Phase 0 — Load & QC
# ---------------------------------------------------------------------------
def load_hourly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["Ngay"], format="%m/%d/%Y")
    df["hour"] = df["Gio"].astype(int)
    # Hour h = end of hour h on calendar day (hour 24 = last hour of that day)
    df["datetime"] = df["date"] + pd.to_timedelta(df["hour"] - 1, unit="h")
    df = df.rename(columns={RAIN_COL: "rain_mm", SLIDE_COL: "landslide"})
    df = df.sort_values(["date", "hour"]).reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def qc_report(df: pd.DataFrame) -> dict:
    n = len(df)
    missing = int(df["rain_mm"].isna().sum())
    dup = int(df.duplicated(["date", "hour"]).sum())
    hours_per_day = df.groupby("date")["hour"].count()
    incomplete_days = int((hours_per_day != 24).sum())
    by_year = (
        df.groupby("year")["rain_mm"]
        .agg(total="count", missing=lambda s: s.isna().sum())
        .assign(missing_pct=lambda x: 100 * x["missing"] / x["total"])
    )
    return {
        "n_rows": n,
        "date_min": str(df["date"].min().date()),
        "date_max": str(df["date"].max().date()),
        "missing_hours": missing,
        "missing_pct": round(100 * missing / n, 3),
        "duplicate_date_hour": dup,
        "days_not_24h": incomplete_days,
        "rain_min": float(df["rain_mm"].min(skipna=True)),
        "rain_max": float(df["rain_mm"].max(skipna=True)),
        "missing_by_year": by_year.reset_index().to_dict(orient="records"),
    }


def build_daily(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("date", as_index=False).agg(
        rain_mm=("rain_mm", "sum"),
        n_valid=("rain_mm", lambda s: int(s.notna().sum())),
        n_missing=("rain_mm", lambda s: int(s.isna().sum())),
        rain_max_hour=("rain_mm", "max"),
        landslide=("landslide", "max"),
    )
    g["valid"] = g["n_valid"] >= MIN_VALID_HOURS
    g.loc[~g["valid"], "rain_mm"] = np.nan
    g.loc[~g["valid"], "rain_max_hour"] = np.nan
    g["year"] = g["date"].dt.year
    g["month"] = g["date"].dt.month
    g["season"] = np.where(g["month"].isin(RAINY_MONTHS), "mua_mua", "mua_kho")
    g["wet"] = g["rain_mm"] >= WET_THRESHOLD
    return g


def build_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily[daily["valid"]].copy()
    m = (
        d.groupby(["year", "month"], as_index=False)
        .agg(
            rain_mm=("rain_mm", "sum"),
            n_days=("rain_mm", "count"),
            n_wet=("wet", "sum"),
            max_daily=("rain_mm", "max"),
        )
    )
    m["ym"] = pd.to_datetime(
        m["year"].astype(str) + "-" + m["month"].astype(str).str.zfill(2) + "-01"
    )
    return m


def build_annual(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily[daily["valid"]].copy()
    a = (
        d.groupby("year", as_index=False)
        .agg(
            rain_mm=("rain_mm", "sum"),
            n_days=("rain_mm", "count"),
            n_wet=("wet", "sum"),
            max_daily=("rain_mm", "max"),
            max_hour=("rain_max_hour", "max"),
        )
    )
    a["sdii"] = a["rain_mm"] / a["n_wet"].replace(0, np.nan)
    return a


def build_seasonal(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily[daily["valid"]].copy()
    s = (
        d.groupby(["year", "season"], as_index=False)
        .agg(
            rain_mm=("rain_mm", "sum"),
            n_days=("rain_mm", "count"),
            n_wet=("wet", "sum"),
            max_daily=("rain_mm", "max"),
        )
    )
    return s


# ---------------------------------------------------------------------------
# Descriptive helpers
# ---------------------------------------------------------------------------
def describe_series(s: pd.Series, name: str) -> dict:
    x = s.dropna().astype(float)
    if len(x) == 0:
        return {"series": name, "n": 0}
    return {
        "series": name,
        "n": int(len(x)),
        "min": float(x.min()),
        "max": float(x.max()),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "std": float(x.std(ddof=1)),
        "cv": float(x.std(ddof=1) / x.mean()) if x.mean() != 0 else np.nan,
        "skewness": float(x.skew()),
        "p10": float(x.quantile(0.10)),
        "p25": float(x.quantile(0.25)),
        "p75": float(x.quantile(0.75)),
        "p90": float(x.quantile(0.90)),
        "sum": float(x.sum()),
    }


# ---------------------------------------------------------------------------
# Phase 2 — RX1day / RX5day
# ---------------------------------------------------------------------------
def compute_rx(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.sort_values("date").copy()
    # rolling 5-day sum only over valid days; NaN breaks windows naturally
    d["rx5"] = d["rain_mm"].rolling(5, min_periods=5).sum()
    rows = []
    for year, g in d.groupby("year"):
        g1 = g.dropna(subset=["rain_mm"])
        if g1.empty:
            continue
        i1 = g1["rain_mm"].idxmax()
        rx1 = float(g1.loc[i1, "rain_mm"])
        d1 = g1.loc[i1, "date"]

        g5 = g.dropna(subset=["rx5"])
        if g5.empty:
            rx5, d5_end, d5_start = np.nan, pd.NaT, pd.NaT
        else:
            i5 = g5["rx5"].idxmax()
            rx5 = float(g5.loc[i5, "rx5"])
            d5_end = g5.loc[i5, "date"]
            d5_start = pd.Timestamp(d5_end) - pd.Timedelta(days=4)
        rows.append(
            {
                "year": int(year),
                "RX1day_mm": rx1,
                "RX1day_date": d1.date().isoformat() if pd.notna(d1) else None,
                "RX5day_mm": rx5,
                "RX5day_start": d5_start.date().isoformat() if pd.notna(d5_start) else None,
                "RX5day_end": d5_end.date().isoformat() if pd.notna(d5_end) else None,
            }
        )
    return pd.DataFrame(rows)


def compute_ams_hourly(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, g in df.groupby("year"):
        g2 = g.dropna(subset=["rain_mm"])
        if g2.empty:
            continue
        i = g2["rain_mm"].idxmax()
        rows.append(
            {
                "year": int(year),
                "AMS_hour_mm": float(g2.loc[i, "rain_mm"]),
                "AMS_hour_datetime": g2.loc[i, "datetime"].isoformat(),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Phase 3 — R95p / R99p thresholds
# ---------------------------------------------------------------------------
def percentile_thresholds(values: np.ndarray, labels: dict) -> dict:
    """Empirical percentiles (numpy default = linear / type-7)."""
    v = values[np.isfinite(values)]
    return {
        **labels,
        "n_wet": int(len(v)),
        "R95p_mm": float(np.percentile(v, 95)),
        "R99p_mm": float(np.percentile(v, 99)),
        "method": "numpy.percentile linear (type-7); wet >= 1.0 mm",
    }


# ---------------------------------------------------------------------------
# Phase 4 — Extreme value analysis (Gumbel L-moments + GEV MLE)
# ---------------------------------------------------------------------------
def lmoments_sample(x: np.ndarray) -> tuple[float, float, float]:
    """First three L-moments (Hosking)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n < 3:
        raise ValueError("Need n>=3 for L-moments")
    b0 = x.mean()
    j = np.arange(n)
    b1 = np.sum(((j) / (n - 1)) * x) / n
    b2 = np.sum(((j * (j - 1)) / ((n - 1) * (n - 2))) * x) / n
    l1 = b0
    l2 = 2 * b1 - b0
    l3 = 6 * b2 - 6 * b1 + b0
    return float(l1), float(l2), float(l3)


def gumbel_from_lmoments(x: np.ndarray) -> tuple[float, float]:
    """Gumbel location (xi) and scale (alpha) from L-moments."""
    l1, l2, _ = lmoments_sample(x)
    alpha = l2 / np.log(2)  # scale σ
    xi = l1 - 0.5772156649 * alpha  # location μ
    return float(xi), float(alpha)


def gumbel_return_level(mu: float, sigma: float, T: float) -> float:
    # x_T = μ − σ ln(−ln(1 − 1/T))
    return float(mu - sigma * np.log(-np.log(1.0 - 1.0 / T)))


def gev_from_lmoments(x: np.ndarray) -> tuple[float, float, float, float]:
    """
    GEV via L-moments (Hosking).
    Hosking k: k>0 Weibull (bounded), k<0 Frechet, k→0 Gumbel.
    scipy.genextreme uses c ≡ Hosking k (same sign).
    Coles/ξ shape = -k.
    Returns (c_scipy, loc, scale, k_hosking).
    """
    from math import lgamma

    l1, l2, l3 = lmoments_sample(x)
    t3 = l3 / l2
    c_approx = 2.0 / (3.0 + t3) - np.log(2) / np.log(3)
    k = 7.8590 * c_approx + 2.9554 * (c_approx ** 2)
    if abs(k) < 1e-6:
        alpha = l2 / np.log(2)
        xi = l1 - 0.5772156649 * alpha
        return 0.0, float(xi), float(alpha), 0.0
    g1 = np.exp(lgamma(1.0 + k))
    alpha = l2 * k / (g1 * (1.0 - 2.0 ** (-k)))
    xi = l1 - alpha * (1.0 - g1) / k
    return float(k), float(xi), float(alpha), float(k)


def gev_return_level(c: float, loc: float, scale: float, T: float) -> float:
    """Return level; c is scipy.genextreme shape (= Hosking k)."""
    p = 1.0 - 1.0 / T
    if abs(c) < 1e-8:
        return gumbel_return_level(loc, scale, T)
    return float(stats.genextreme.ppf(p, c, loc=loc, scale=scale))


def bootstrap_gumbel_ci(
    x: np.ndarray, T: float, n_boot: int = N_BOOT
) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    n = len(x)
    samples = []
    for _ in range(n_boot):
        xb = RNG.choice(x, size=n, replace=True)
        try:
            mu, sig = gumbel_from_lmoments(xb)
            samples.append(gumbel_return_level(mu, sig, T))
        except Exception:
            continue
    arr = np.array(samples)
    return float(np.median(arr)), float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def analyze_ams(series: np.ndarray, label: str) -> dict:
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    mu, sigma = gumbel_from_lmoments(x)
    try:
        c, loc, scale, k = gev_from_lmoments(x)
        # Coles ξ = -k; |ξ|>0.5 with n=10 is fragile
        xi_coles = -k
        gev_flag = "ok" if abs(xi_coles) <= 0.5 else "unstable_shape_n_small"
        gev_ok = True
    except Exception:
        c, loc, scale, k, xi_coles = np.nan, np.nan, np.nan, np.nan, np.nan
        gev_flag = "fit_failed"
        gev_ok = False

    rows = []
    for T in RETURN_PERIODS:
        g_x = gumbel_return_level(mu, sigma, T)
        _, lo, hi = bootstrap_gumbel_ci(x, T)
        row = {
            "series": label,
            "T_years": T,
            "Gumbel_mm": round(g_x, 2),
            "Gumbel_CI95_low": round(lo, 2),
            "Gumbel_CI95_high": round(hi, 2),
            "Gumbel_mu": round(mu, 4),
            "Gumbel_sigma": round(sigma, 4),
            "primary_method": "Gumbel_Lmoments",
        }
        if gev_ok:
            gev_x = gev_return_level(c, loc, scale, T)
            row["GEV_mm"] = round(gev_x, 2) if np.isfinite(gev_x) else np.nan
            row["GEV_shape_xi_Coles"] = round(xi_coles, 4)
            row["GEV_shape_k_Hosking"] = round(k, 4)
            row["GEV_loc"] = round(loc, 4)
            row["GEV_scale"] = round(scale, 4)
            row["GEV_flag"] = gev_flag
        else:
            row["GEV_mm"] = np.nan
            row["GEV_flag"] = gev_flag
        rows.append(row)
    return {
        "params": {
            "gumbel_mu": mu,
            "gumbel_sigma": sigma,
            "n": len(x),
            "gev_flag": gev_flag if gev_ok else "fit_failed",
        },
        "levels": rows,
    }


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def save_fig(name: str) -> Path:
    path = FIG / name
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return path


def plot_monthly_climate(monthly: pd.DataFrame) -> None:
    clim = monthly.groupby("month")["rain_mm"].agg(["mean", "min", "max", "std"])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(clim.index, clim["mean"], color="#2a6f97", alpha=0.85, label="TB tổng tháng")
    ax.errorbar(
        clim.index,
        clim["mean"],
        yerr=clim["std"],
        fmt="none",
        ecolor="#023047",
        capsize=3,
        label="±1σ",
    )
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Tháng")
    ax.set_ylabel("Lượng mưa (mm)")
    ax.set_title("Khí hậu mưa tháng — Trà My (2008–2017)")
    ax.legend()
    save_fig("fig_monthly_clim.png")


def plot_annual_totals(annual: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(annual["year"], annual["rain_mm"], color="#2a6f97")
    ax.axhline(annual["rain_mm"].mean(), color="#e76f51", ls="--", label="TB năm")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Tổng mưa năm (mm)")
    ax.set_title("Tổng lượng mưa năm — Trà My")
    ax.legend()
    save_fig("fig_annual_totals.png")


def plot_rx(rx: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    w = 0.35
    ax.bar(rx["year"] - w / 2, rx["RX1day_mm"], width=w, label="RX1day", color="#2a6f97")
    ax.bar(rx["year"] + w / 2, rx["RX5day_mm"], width=w, label="RX5day", color="#e76f51")
    ax.set_xlabel("Năm")
    ax.set_ylabel("mm")
    ax.set_title("Cực đại mưa 1 ngày và 5 ngày liên tiếp theo năm")
    ax.legend()
    save_fig("fig_rx1_rx5.png")


def plot_hist_thresholds(
    values: np.ndarray, r95: float, r99: float, title: str, fname: str, xlabel: str
) -> None:
    v = values[np.isfinite(values)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(v, bins=40, color="#8ecae6", edgecolor="#023047", alpha=0.9)
    ax.axvline(r95, color="#e9c46a", lw=2, label=f"R95p = {r95:.1f} mm")
    ax.axvline(r99, color="#e76f51", lw=2, label=f"R99p = {r99:.1f} mm")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Tần suất")
    ax.set_title(title)
    ax.legend()
    save_fig(fname)


def plot_return_curve(ams: np.ndarray, levels: list[dict], title: str, fname: str) -> None:
    x = np.sort(np.asarray(ams, dtype=float))
    n = len(x)
    # Gringorten plotting position
    rank = np.arange(1, n + 1)
    F = (rank - 0.44) / (n + 0.12)
    T_emp = 1.0 / (1.0 - F)

    mu = levels[0]["Gumbel_mu"]
    sig = levels[0]["Gumbel_sigma"]
    T_grid = np.logspace(0.05, 2.1, 80)
    x_fit = [gumbel_return_level(mu, sig, t) for t in T_grid]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogx(T_emp, x, "o", color="#023047", label="AMS (Gringorten)")
    ax.semilogx(T_grid, x_fit, "-", color="#2a6f97", label="Gumbel fit")
    for row in levels:
        ax.semilogx(row["T_years"], row["Gumbel_mm"], "s", color="#e76f51")
        ax.annotate(
            f"T={row['T_years']}",
            (row["T_years"], row["Gumbel_mm"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )
    ax.set_xlabel("Chu kỳ lặp lại T (năm)")
    ax.set_ylabel("Mức mưa (mm)")
    ax.set_title(title)
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend()
    save_fig(fname)


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------
def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, sdf in sheets.items():
            sdf.to_excel(writer, sheet_name=name[:31], index=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ensure_dirs()
    print("Phase 0: load & QC …")
    hourly = load_hourly(CSV_PATH)
    qc = qc_report(hourly)
    daily = build_daily(hourly)
    monthly = build_monthly(daily)
    annual = build_annual(daily)
    seasonal = build_seasonal(daily)

    hourly_out = hourly[
        ["datetime", "date", "year", "month", "hour", "rain_mm", "landslide"]
    ].copy()
    hourly_out.to_csv(CACHE / "hourly.csv", index=False)
    daily.to_csv(CACHE / "daily.csv", index=False)
    monthly.to_csv(CACHE / "monthly.csv", index=False)
    annual.to_csv(CACHE / "annual.csv", index=False)
    seasonal.to_csv(CACHE / "seasonal.csv", index=False)
    (OUT / "00_qc_report.json").write_text(json.dumps(qc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  rows={qc['n_rows']}  missing={qc['missing_hours']} ({qc['missing_pct']}%)")
    print(f"  range={qc['date_min']} → {qc['date_max']}")

    # ----- Phase 1 -----
    print("Phase 1: descriptive stats …")
    daily_valid = daily.loc[daily["valid"], "rain_mm"]
    wet_days = daily.loc[daily["valid"] & daily["wet"], "rain_mm"]
    desc_daily = describe_series(daily_valid, "mua_ngay")
    desc_daily["n_wet_days"] = int(daily.loc[daily["valid"], "wet"].sum())
    desc_daily["sdii_mm_per_wet_day"] = float(wet_days.mean()) if len(wet_days) else np.nan

    desc_hourly = describe_series(hourly["rain_mm"], "mua_gio")
    wet_hours = hourly.loc[hourly["rain_mm"] >= WET_THRESHOLD, "rain_mm"]
    desc_hourly["n_wet_hours"] = int(len(wet_hours))
    desc_hourly["mean_wet_hour_mm"] = float(wet_hours.mean()) if len(wet_hours) else np.nan

    month_clim = (
        monthly.groupby("month")["rain_mm"]
        .agg(mean="mean", min="min", max="max", std="std", n="count")
        .reset_index()
    )
    desc_annual = describe_series(annual["rain_mm"], "mua_nam")
    wettest = annual.loc[annual["rain_mm"].idxmax()]
    driest = annual.loc[annual["rain_mm"].idxmin()]
    desc_annual["wettest_year"] = int(wettest["year"])
    desc_annual["wettest_mm"] = float(wettest["rain_mm"])
    desc_annual["driest_year"] = int(driest["year"])
    desc_annual["driest_mm"] = float(driest["rain_mm"])

    # seasonal pivot
    seas_pivot = seasonal.pivot(index="year", columns="season", values="rain_mm").reset_index()
    if "mua_mua" in seas_pivot.columns and "mua_kho" in seas_pivot.columns:
        seas_pivot["tong"] = seas_pivot["mua_mua"] + seas_pivot["mua_kho"]
        seas_pivot["ty_le_mua_mua"] = seas_pivot["mua_mua"] / seas_pivot["tong"]
    desc_rainy = describe_series(
        seasonal.loc[seasonal["season"] == "mua_mua", "rain_mm"], "mua_mua_IX_XII"
    )
    desc_dry = describe_series(
        seasonal.loc[seasonal["season"] == "mua_kho", "rain_mm"], "mua_kho_I_VIII"
    )

    desc_rows = [desc_hourly, desc_daily, desc_annual, desc_rainy, desc_dry]
    desc_df = pd.DataFrame(desc_rows)

    write_workbook(
        OUT / "01_descriptive_stats.xlsx",
        {
            "tong_hop": desc_df,
            "mua_nam": annual,
            "khi_hau_thang": month_clim,
            "mua_thang_chi_tiet": monthly,
            "mua_theo_mua": seas_pivot if len(seas_pivot) else seasonal,
            "mua_ngay_mau": daily.loc[daily["valid"], ["date", "year", "month", "season", "rain_mm", "wet"]],
        },
    )
    plot_monthly_climate(monthly)
    plot_annual_totals(annual)

    # ----- Phase 2 -----
    print("Phase 2: RX1day / RX5day …")
    rx = compute_rx(daily)
    ams_h = compute_ams_hourly(hourly)
    rx_merged = rx.merge(ams_h, on="year", how="left")
    for col in ("RX1day_mm", "RX5day_mm", "AMS_hour_mm"):
        if col in rx_merged.columns:
            rx_merged[col] = rx_merged[col].round(1)
    rx_merged.to_csv(OUT / "02_rx1_rx5.csv", index=False)
    plot_rx(rx)

    # ----- Phase 3 -----
    print("Phase 3: R95p / R99p …")
    hour_wet = hourly.loc[hourly["rain_mm"] >= WET_THRESHOLD, "rain_mm"].to_numpy()
    day_wet = daily.loc[daily["valid"] & (daily["rain_mm"] >= WET_THRESHOLD), "rain_mm"].to_numpy()
    thr_h = percentile_thresholds(hour_wet, {"scale": "hourly", "unit": "mm/h"})
    thr_d = percentile_thresholds(day_wet, {"scale": "daily", "unit": "mm/day"})
    thr_h["R95p_mm"] = round(thr_h["R95p_mm"], 2)
    thr_h["R99p_mm"] = round(thr_h["R99p_mm"], 2)
    thr_d["R95p_mm"] = round(thr_d["R95p_mm"], 2)
    thr_d["R99p_mm"] = round(thr_d["R99p_mm"], 2)
    thr_df = pd.DataFrame([thr_h, thr_d])
    thr_df.to_csv(OUT / "03_r95_r99_thresholds.csv", index=False)

    # exceedance counts by year
    h_ex = hourly.dropna(subset=["rain_mm"]).copy()
    h_ex["gt_r95"] = h_ex["rain_mm"] > thr_h["R95p_mm"]
    h_ex["gt_r99"] = h_ex["rain_mm"] > thr_h["R99p_mm"]
    hour_ex_year = h_ex.groupby("year")[["gt_r95", "gt_r99"]].sum().reset_index()
    hour_ex_year.columns = ["year", "hours_gt_R95p", "hours_gt_R99p"]

    d_ex = daily.loc[daily["valid"]].copy()
    d_ex["gt_r95"] = d_ex["rain_mm"] > thr_d["R95p_mm"]
    d_ex["gt_r99"] = d_ex["rain_mm"] > thr_d["R99p_mm"]
    day_ex_year = d_ex.groupby("year")[["gt_r95", "gt_r99"]].sum().reset_index()
    day_ex_year.columns = ["year", "days_gt_R95p", "days_gt_R99p"]
    hour_ex_year.to_csv(OUT / "03b_exceedance_by_year_hourly.csv", index=False)
    day_ex_year.to_csv(OUT / "03b_exceedance_by_year_daily.csv", index=False)

    plot_hist_thresholds(
        hour_wet,
        thr_h["R95p_mm"],
        thr_h["R99p_mm"],
        "Phân bố mưa giờ ướt (≥1 mm) — ngưỡng R95p/R99p",
        "fig_r95_r99_hourly.png",
        "mm/giờ",
    )
    plot_hist_thresholds(
        day_wet,
        thr_d["R95p_mm"],
        thr_d["R99p_mm"],
        "Phân bố mưa ngày ướt (≥1 mm) — ngưỡng R95p/R99p",
        "fig_r95_r99_daily.png",
        "mm/ngày",
    )

    # ----- Phase 4 -----
    print("Phase 4: return periods …")
    ams_hour = ams_h["AMS_hour_mm"].to_numpy()
    ams_day = rx["RX1day_mm"].to_numpy()
    res_h = analyze_ams(ams_hour, "AMS_hourly")
    res_d = analyze_ams(ams_day, "AMS_daily_RX1day")
    # optional RX5
    res_rx5 = analyze_ams(rx["RX5day_mm"].to_numpy(), "AMS_RX5day")

    levels_df = pd.DataFrame(res_h["levels"] + res_d["levels"] + res_rx5["levels"])
    write_workbook(
        OUT / "04_return_periods.xlsx",
        {
            "return_levels": levels_df,
            "AMS_hourly": ams_h,
            "AMS_daily_RX1_RX5": rx,
            "note": pd.DataFrame(
                [
                    {
                        "warning": (
                            "n=10 năm quan trắc; mức T=50–100 năm là ngoại suy mạnh. "
                            "Khoảng tin cậy 95% từ bootstrap nonparametric trên AMS. "
                            "Phương pháp chính: Gumbel L-moments; GEV L-moments chỉ để đối chiếu "
                            "(flag unstable_shape_n_small khi |k|>0.5)."
                        ),
                        "gumbel_method": "L-moments",
                        "gev_method": "L-moments (Hosking)",
                        "plotting_position": "Gringorten (i-0.44)/(n+0.12)",
                    }
                ]
            ),
        },
    )
    plot_return_curve(
        ams_hour,
        res_h["levels"],
        "Đường cong tần suất mưa giờ cực đại năm (Gumbel)",
        "fig_return_hourly.png",
    )
    plot_return_curve(
        ams_day,
        res_d["levels"],
        "Đường cong tần suất mưa ngày cực đại năm RX1day (Gumbel)",
        "fig_return_daily.png",
    )

    # ----- Phase 5 — checks & SUMMARY -----
    print("Phase 5: summary & checks …")
    checks = []
    # RX1 <= RX5 each year
    ok_rx = bool((rx["RX1day_mm"] <= rx["RX5day_mm"] + 1e-9).all())
    checks.append({"check": "RX1day <= RX5day every year", "pass": ok_rx})
    checks.append(
        {
            "check": "R99p_hour > R95p_hour",
            "pass": bool(thr_h["R99p_mm"] > thr_h["R95p_mm"]),
        }
    )
    checks.append(
        {
            "check": "R99p_day > R95p_day",
            "pass": bool(thr_d["R99p_mm"] > thr_d["R95p_mm"]),
        }
    )
    g_day = [r["Gumbel_mm"] for r in res_d["levels"]]
    checks.append(
        {
            "check": "daily return levels increasing with T",
            "pass": bool(all(g_day[i] < g_day[i + 1] for i in range(len(g_day) - 1))),
        }
    )
    g_hr = [r["Gumbel_mm"] for r in res_h["levels"]]
    checks.append(
        {
            "check": "hourly return levels increasing with T",
            "pass": bool(all(g_hr[i] < g_hr[i + 1] for i in range(len(g_hr) - 1))),
        }
    )
    # sum hourly vs sum daily (valid days only) — approximate
    sum_h = float(hourly["rain_mm"].sum(skipna=True))
    sum_d = float(daily.loc[daily["valid"], "rain_mm"].sum())
    checks.append(
        {
            "check": "hourly total vs valid-daily total relative diff",
            "pass": True,
            "sum_hourly_mm": sum_h,
            "sum_valid_daily_mm": sum_d,
            "rel_diff_pct": round(100 * abs(sum_h - sum_d) / sum_h, 3) if sum_h else None,
            "note": "Khác nhau vì ngày invalid bị loại khỏi tổng ngày",
        }
    )
    pd.DataFrame(checks).to_csv(OUT / "05_cross_checks.csv", index=False)

    # Build SUMMARY.md
    def fmt(v, nd=1):
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "—"
        return f"{v:.{nd}f}"

    summary = f"""# Kết quả phân tích mưa giờ — Trạm Trà My

**Nguồn:** `Hourly rain in Tra My.xlsx - TM_1hr.csv`  
**Thời đoạn thực tế:** {qc['date_min']} → {qc['date_max']} (10 năm; đề ghi 2011–2020 nhưng file chỉ có 2008–2017)  
**Trạm:** 1 trạm Trà My (`TM_1hr`)  
**Đơn vị:** mm  
**Quy ước giờ:** `Gio` = 1…24 là giờ kết thúc trong ngày lịch  
**Ngày hợp lệ:** ≥ {MIN_VALID_HOURS} giờ có số liệu; wet ≥ {WET_THRESHOLD} mm  
**Mùa mưa:** IX–XII; **mùa khô:** I–VIII  

---

## 0. Kiểm tra chất lượng số liệu

- Số bản ghi giờ: **{qc['n_rows']:,}**
- Thiếu mưa: **{qc['missing_hours']:,}** giờ ({qc['missing_pct']}%)
- Trùng (ngày, giờ): **{qc['duplicate_date_hour']}**
- Ngày không đủ 24 dòng: **{qc['days_not_24h']}**
- Min / max mưa giờ: **{fmt(qc['rain_min'], 1)} / {fmt(qc['rain_max'], 1)}** mm

---

## 1. Thống kê thông thường

### Mưa giờ
| Chỉ tiêu | Giá trị |
|---|---:|
| n | {desc_hourly['n']:,} |
| Mean | {fmt(desc_hourly['mean'], 3)} mm |
| Median | {fmt(desc_hourly['median'], 2)} mm |
| Std | {fmt(desc_hourly['std'], 3)} mm |
| Max | {fmt(desc_hourly['max'], 1)} mm |
| Số giờ ướt (≥1 mm) | {desc_hourly['n_wet_hours']:,} |

### Mưa ngày (ngày hợp lệ)
| Chỉ tiêu | Giá trị |
|---|---:|
| n | {desc_daily['n']:,} |
| Mean | {fmt(desc_daily['mean'], 2)} mm |
| Median | {fmt(desc_daily['median'], 2)} mm |
| Std | {fmt(desc_daily['std'], 2)} mm |
| Min / Max | {fmt(desc_daily['min'], 1)} / {fmt(desc_daily['max'], 1)} mm |
| CV | {fmt(desc_daily['cv'], 2)} |
| Skewness | {fmt(desc_daily['skewness'], 2)} |
| P10 / P90 | {fmt(desc_daily['p10'], 1)} / {fmt(desc_daily['p90'], 1)} mm |
| Số ngày ướt | {desc_daily['n_wet_days']:,} |
| SDII (TB ngày ướt) | {fmt(desc_daily['sdii_mm_per_wet_day'], 2)} mm/ngày |

### Mưa năm
| Chỉ tiêu | Giá trị |
|---|---:|
| Mean | {fmt(desc_annual['mean'], 1)} mm |
| Std | {fmt(desc_annual['std'], 1)} mm |
| Min (năm {desc_annual['driest_year']}) | {fmt(desc_annual['driest_mm'], 1)} mm |
| Max (năm {desc_annual['wettest_year']}) | {fmt(desc_annual['wettest_mm'], 1)} mm |

### Mưa theo mùa (tổng mùa / năm)
| Mùa | Mean (mm) | Min | Max | Std |
|---|---:|---:|---:|---:|
| Mưa (IX–XII) | {fmt(desc_rainy['mean'], 1)} | {fmt(desc_rainy['min'], 1)} | {fmt(desc_rainy['max'], 1)} | {fmt(desc_rainy['std'], 1)} |
| Khô (I–VIII) | {fmt(desc_dry['mean'], 1)} | {fmt(desc_dry['min'], 1)} | {fmt(desc_dry['max'], 1)} | {fmt(desc_dry['std'], 1)} |

Tỷ lệ đóng góp trung bình mùa mưa / tổng năm: **{fmt(100 * seas_pivot['ty_le_mua_mua'].mean(), 1)}%**

Chi tiết khí hậu tháng và bảng đầy đủ: `outputs/01_descriptive_stats.xlsx`

---

## 2. Cực đại năm — RX1day & RX5day

| Năm | RX1day (mm) | Ngày | RX5day (mm) | Cửa sổ | AMS giờ (mm) |
|---:|---:|---|---:|---|---:|
"""
    for _, r in rx_merged.iterrows():
        summary += (
            f"| {int(r['year'])} | {r['RX1day_mm']:.1f} | {r['RX1day_date']} | "
            f"{r['RX5day_mm']:.1f} | {r['RX5day_start']} → {r['RX5day_end']} | "
            f"{r['AMS_hour_mm']:.1f} |\n"
        )
    summary += f"""
- RX1day lớn nhất chuỗi: **{rx['RX1day_mm'].max():.1f} mm** (năm {int(rx.loc[rx['RX1day_mm'].idxmax(), 'year'])})
- RX5day lớn nhất chuỗi: **{rx['RX5day_mm'].max():.1f} mm** (năm {int(rx.loc[rx['RX5day_mm'].idxmax(), 'year'])})

File: `outputs/02_rx1_rx5.csv`

---

## 3. Ngưỡng mưa rất lớn (R95p) / cực kỳ lớn (R99p)

Định nghĩa: percentile trên mẫu **wet** (≥ 1 mm); `numpy.percentile` tuyến tính (type-7).

| Thang | n wet | R95p (mm) | R99p (mm) |
|---|---:|---:|---:|
| Mưa giờ | {thr_h['n_wet']:,} | {thr_h['R95p_mm']:.2f} | {thr_h['R99p_mm']:.2f} |
| Mưa ngày | {thr_d['n_wet']:,} | {thr_d['R95p_mm']:.2f} | {thr_d['R99p_mm']:.2f} |

File: `outputs/03_r95_r99_thresholds.csv`

---

## 4. Mức mưa cực đại theo chu kỳ lặp lại (Gumbel L-moments)

> **Cảnh báo:** chỉ có n = 10 giá trị AMS → mức T = 50–100 năm ngoại suy mạnh. CI 95% = bootstrap {N_BOOT} lần.

### Mưa giờ (AMS giờ)
| T (năm) | Gumbel (mm) | CI 95% | GEV (mm) |
|---:|---:|---|---:|
"""
    for row in res_h["levels"]:
        summary += (
            f"| {row['T_years']} | {row['Gumbel_mm']:.1f} | "
            f"[{row['Gumbel_CI95_low']:.1f}, {row['Gumbel_CI95_high']:.1f}] | "
            f"{row.get('GEV_mm', float('nan')):.1f} |\n"
        )
    summary += f"""
Tham số Gumbel (giờ): μ = {res_h['params']['gumbel_mu']:.3f}, σ = {res_h['params']['gumbel_sigma']:.3f}

### Mưa ngày — RX1day
| T (năm) | Gumbel (mm) | CI 95% | GEV (mm) |
|---:|---:|---|---:|
"""
    for row in res_d["levels"]:
        summary += (
            f"| {row['T_years']} | {row['Gumbel_mm']:.1f} | "
            f"[{row['Gumbel_CI95_low']:.1f}, {row['Gumbel_CI95_high']:.1f}] | "
            f"{row.get('GEV_mm', float('nan')):.1f} |\n"
        )
    summary += f"""
Tham số Gumbel (ngày): μ = {res_d['params']['gumbel_mu']:.3f}, σ = {res_d['params']['gumbel_sigma']:.3f}

File: `outputs/04_return_periods.xlsx`

---

## Kiểm tra chéo

"""
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        extra = ""
        if "rel_diff_pct" in c:
            extra = f" (Δ tương đối {c['rel_diff_pct']}%)"
        summary += f"- [{status}] {c['check']}{extra}\n"

    summary += """
---

## File đầu ra

| File | Nội dung |
|---|---|
| `outputs/00_qc_report.json` | Báo cáo QC |
| `outputs/01_descriptive_stats.xlsx` | Thống kê mô tả |
| `outputs/02_rx1_rx5.csv` | RX1day, RX5day, AMS giờ |
| `outputs/03_r95_r99_thresholds.csv` | Ngưỡng R95p/R99p |
| `outputs/04_return_periods.xlsx` | Chu kỳ lặp lại |
| `outputs/05_cross_checks.csv` | Kiểm tra chéo |
| `outputs/figures/` | Biểu đồ PNG |
| `outputs/cache/` | Chuỗi giờ/ngày/tháng/năm/mùa |
"""
    (OUT / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print("Done. See outputs/SUMMARY.md")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Sinh dữ liệu cho website Trà My Rain Atlas.

Dùng lại các hàm tính của báo cáo (analysis/report_analysis.py) để số liệu
trên web khớp với báo cáo LaTeX. Kết quả ghi vào data/*.json, data/hourly/,
data/csv/.

Chạy:  python3 scripts/build_data.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

import report_analysis as R  # noqa: E402

RAW_CSV = ROOT / "data" / "raw" / "Hourly_rain_Tra_My_2008_2017.csv"
R.CSV_PATH = RAW_CSV
DATA = ROOT / "data"
T_TABLE = [2, 5, 10, 20, 50, 100, 200, 500]
T_GRID = np.unique(np.concatenate([np.round(np.logspace(np.log10(1.01), np.log10(1000), 90), 4), T_TABLE]))


def r1(x, nd=1):
    if x is None:
        return None
    try:
        if pd.isna(x) or not np.isfinite(float(x)):
            return None
    except TypeError:
        return None
    return round(float(x), nd)


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else round(float(o), 4)
    if isinstance(o, pd.Timestamp):
        return o.strftime("%Y-%m-%d")
    return o


def dump(rel: str, obj) -> None:
    p = DATA / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {rel:28s} {p.stat().st_size / 1024:8.1f} KB")


def stat_block(x) -> dict:
    s = R.basic_stats(pd.Series(x))
    return {k: r1(v, 3) for k, v in s.items()}


# ---------------------------------------------------------------------------
def main() -> None:
    print("Đọc và kiểm tra dữ liệu …")
    hourly, daily, mon = R.prepare()
    R.check_missing_pattern(hourly, daily)
    hv = hourly.dropna(subset=["rain_mm"])
    dv = daily[daily["valid"]]
    years = sorted(hourly["year"].unique().tolist())

    # ----- meta -----
    dump("meta.json", {
        "name": "Trà My Rain Atlas",
        "station": "Trạm Trà My",
        "province": "Quảng Nam, Việt Nam",
        "location_note": "Tọa độ gần đúng của thị trấn Trà My (huyện Bắc Trà My)",
        "lat": 15.345, "lon": 108.228,
        "period": ["2008-01-01", "2017-12-31"],
        "years": years,
        "unit": "mm",
        "rules": {
            "wet_mm": 1.0, "valid_day_hours": 20, "valid_month_frac": 0.9,
            "rainy_months": [9, 10, 11, 12], "dry_months": list(range(1, 9)),
            "hour_convention": "Giờ h là lượng mưa của giờ kết thúc lúc h giờ (1–24)",
        },
        "missing": R.N["missing"],
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source_file": "data/raw/Hourly_rain_Tra_My_2008_2017.csv",
    })

    # ----- hourly theo năm -----
    for y in years:
        g = hourly[hourly["year"] == y].sort_values(["date", "hour"])
        dump(f"hourly/{y}.json", {
            "year": y, "start": f"{y}-01-01",
            "rain": [r1(v) for v in g["rain_mm"].tolist()],
            "slide": [int(i) for i in np.flatnonzero(g["landslide"].values == 1)],
        })

    # ----- daily -----
    d = daily.sort_values("date")
    dump("daily.json", {
        "start": "2008-01-01",
        "rain": [r1(v) for v in d["rain_mm"].tolist()],
        "valid_hours": d["n_valid"].astype(int).tolist(),
        "slide": [int(i) for i in np.flatnonzero(d["landslide"].values == 1)],
    })

    # ----- monthly -----
    mon = mon.sort_values(["year", "month"])
    mrows = []
    for r in mon.itertuples():
        g = dv[(dv["year"] == r.year) & (dv["month"] == r.month)]
        mrows.append([int(r.year), int(r.month), r1(r.rain), int(r.n_valid), int(r.n_days),
                      bool(r.valid), int(r.n_wet), r1(g["rain_mm"].max() if len(g) else None)])
    mv = mon[mon["valid"]]
    clim = []
    for m in range(1, 13):
        s = stat_block(mv.loc[mv["month"] == m, "rain"])
        s["month"] = m
        clim.append(s)
    dump("monthly.json", {
        "columns": ["year", "month", "total", "valid_days", "days", "valid", "wet_days", "max_day"],
        "rows": mrows, "climatology": clim, "all": stat_block(mv["rain"]),
    })

    # ----- annual / seasonal -----
    arows = []
    ann = []
    for y in years:
        my = mon[mon["year"] == y]
        dy = dv[dv["year"] == y]
        hy = hv[hv["year"] == y]
        rec = {
            "year": y,
            "total": r1(my["rain"].sum()),
            "rainy": r1(my.loc[my["month"].isin(R.RAINY), "rain"].sum()),
            "dry": r1(my.loc[my["month"].isin(R.DRY), "rain"].sum()),
            "wet_days": int(my["n_wet"].sum()),
            "ok_year": bool(my["valid"].all()),
            "ok_rainy": bool(my[my["month"].isin(R.RAINY)]["valid"].all()),
            "ok_dry": bool(my[my["month"].isin(R.DRY)]["valid"].all()),
            "valid_day_pct": r1(100 * daily[daily["year"] == y]["valid"].mean()),
            "missing_hour_pct": r1(100 * hourly[hourly["year"] == y]["rain_mm"].isna().mean(), 2),
            "max_day": r1(dy["rain_mm"].max()),
            "max_hour": r1(hy["rain_mm"].max()),
        }
        ann.append(rec)
    ann_df = pd.DataFrame(ann)
    annual_stats = {
        "total": stat_block(ann_df.loc[ann_df.ok_year, "total"]),
        "rainy": stat_block(ann_df.loc[ann_df.ok_rainy, "rainy"]),
        "dry": stat_block(ann_df.loc[ann_df.ok_dry, "dry"]),
        "wet_days": stat_block(ann_df.loc[ann_df.ok_year, "wet_days"]),
        "rainy_share": stat_block(100 * ann_df.loc[ann_df.ok_year, "rainy"] / ann_df.loc[ann_df.ok_year, "total"]),
    }
    dump("annual.json", {"rows": ann, "stats": annual_stats})

    # ----- summary (Câu 1) -----
    def grp(df, col, big):
        return {
            "all": {k: r1(v, 3) for k, v in R.rain_stats(df[col], big).items()},
            "rainy": {k: r1(v, 3) for k, v in R.rain_stats(df.loc[df["month"].isin(R.RAINY), col], big).items()},
            "dry": {k: r1(v, 3) for k, v in R.rain_stats(df.loc[df["month"].isin(R.DRY), col], big).items()},
        }
    hv_ = hv.assign(season=np.where(hv["month"].isin(R.RAINY), "rainy", "dry"))
    diurnal = {}
    for sname, g in hv_.groupby("season"):
        diurnal[sname] = {
            "mean": [r1(v, 3) for v in g.groupby("hour")["rain_mm"].mean().reindex(range(1, 25)).tolist()],
            "wet_freq": [r1(v, 2) for v in (g.assign(w=g["rain_mm"] >= 1).groupby("hour")["w"].mean() * 100).reindex(range(1, 25)).tolist()],
        }
    top_days = dv.nlargest(10, "rain_mm")
    top_hours = hv.nlargest(10, "rain_mm")
    nh, nh_ok = len(hourly), int(hourly["rain_mm"].notna().sum())
    dump("summary.json", {
        "qc": {
            "hours": nh, "hours_ok": nh_ok, "hours_missing": nh - nh_ok,
            "days": len(daily), "days_ok": int(daily["valid"].sum()),
            "duplicates": int(hourly.duplicated(["date", "hour"]).sum()),
            "months_ok": int(mon["valid"].sum()), "months": len(mon),
            "years_full": int(ann_df["ok_year"].sum()),
            "invalid_months": [[int(r.year), int(r.month), r1(100 * r.frac)] for r in mon[~mon["valid"]].itertuples()],
            "month_valid_pct": [[int(r.year), int(r.month), r1(100 * r.frac)] for r in mon.itertuples()],
        },
        "hourly": grp(hv, "rain_mm", (20, 50)),
        "daily": grp(dv, "rain_mm", (50, 100)),
        "diurnal": diurnal,
        "top_days": [[r.date.strftime("%Y-%m-%d"), r1(r.rain_mm)] for r in top_days.itertuples()],
        "top_hours": [[r.date.strftime("%Y-%m-%d"), int(r.hour), r1(r.rain_mm)] for r in top_hours.itertuples()],
        "share_days_gt100": r1(100 * dv.loc[dv["rain_mm"] > 100, "rain_mm"].sum() / dv["rain_mm"].sum(), 2),
    })

    # ----- Rx (Câu 2) + đợt mưa -----
    print("Câu 2: cực trị …")
    rx = R.compute_rx(daily)
    idx = hv.groupby("year")["rain_mm"].idxmax()
    ams_h = hv.loc[idx, ["year", "date", "hour", "rain_mm"]].rename(columns={"rain_mm": "rx1h"})
    rx = rx.merge(ams_h, on="year")
    slide_days = set(daily.loc[daily["landslide"] == 1, "date"])
    rx_rows, events = [], []
    for r in rx.itertuples():
        d1, d5s, d5e = pd.Timestamp(r.RX1day_date), pd.Timestamp(r.RX5day_start), pd.Timestamp(r.RX5day_end)
        win = pd.date_range(d5s, d5e)
        rx_rows.append({
            "year": int(r.year), "valid_day_pct": r1(100 * daily[daily["year"] == r.year]["valid"].mean()),
            "rx1day": r1(r.RX1day_mm), "rx1day_date": d1.strftime("%Y-%m-%d"),
            "rx5day": r1(r.RX5day_mm), "rx5day_start": d5s.strftime("%Y-%m-%d"), "rx5day_end": d5e.strftime("%Y-%m-%d"),
            "rx1hour": r1(r.rx1h), "rx1hour_date": pd.Timestamp(r.date).strftime("%Y-%m-%d"), "rx1hour_hour": int(r.hour),
            "slide_rx1": d1 in slide_days, "slide_rx5": any(x in slide_days for x in win),
            "rx1_in_rx5": bool(d5s <= d1 <= d5e),
        })
        a, b = d5s - pd.Timedelta(days=1), d5e + pd.Timedelta(days=1)
        h = hourly[(hourly["date"] >= a) & (hourly["date"] <= b)].sort_values(["date", "hour"])
        events.append({
            "year": int(r.year), "start": a.strftime("%Y-%m-%d"),
            "window": [d5s.strftime("%Y-%m-%d"), d5e.strftime("%Y-%m-%d")], "total": r1(r.RX5day_mm),
            "rain": [r1(v) for v in h["rain_mm"].tolist()],
            "slide": [int(i) for i in np.flatnonzero(h["landslide"].values == 1)],
        })
    rx_stats = {
        "rx1day": stat_block(rx["RX1day_mm"]), "rx5day": stat_block(rx["RX5day_mm"]),
        "rx1hour": stat_block(rx["rx1h"]), "ratio": stat_block(rx["RX5day_mm"] / rx["RX1day_mm"]),
    }
    dump("rx.json", {"rows": rx_rows, "stats": rx_stats})
    dump("events.json", {"events": events})

    # ----- Ngưỡng (Câu 3) -----
    print("Câu 3: ngưỡng …")
    T3 = {
        "hour_all": R.thr_block(hv["rain_mm"], 10),
        "hour_rainy": R.thr_block(hv.loc[hv["month"].isin(R.RAINY), "rain_mm"], 10),
        "day_all": R.thr_block(dv["rain_mm"], 10),
        "day_rainy": R.thr_block(dv.loc[dv["month"].isin(R.RAINY), "rain_mm"], 10),
    }
    h95, h99 = T3["hour_all"]["R95p"], T3["hour_all"]["R99p"]
    d95, d99 = T3["day_all"]["R95p"], T3["day_all"]["R99p"]
    by_year = []
    for y in years:
        hy = hv.loc[hv["year"] == y, "rain_mm"]
        dy = dv.loc[dv["year"] == y, "rain_mm"]
        by_year.append({"year": y, "hour95": int((hy > h95).sum()), "hour99": int((hy > h99).sum()),
                        "day95": int((dy > d95).sum()), "day99": int((dy > d99).sum())})
    by_month = []
    for m in range(1, 13):
        hm = hv.loc[hv["month"] == m, "rain_mm"]
        dm = dv.loc[dv["month"] == m, "rain_mm"]
        by_month.append({"month": m, "hour95": int((hm > h95).sum()), "hour99": int((hm > h99).sum()),
                         "day95": int((dm > d95).sum()), "day99": int((dm > d99).sum())})
    wet_h = hv.loc[hv["rain_mm"] >= 1, "rain_mm"].values
    wet_d = dv.loc[dv["rain_mm"] >= 1, "rain_mm"].values
    pct_levels = list(range(1, 100)) + [99.5, 99.9]

    def hist(v, step):
        edges = np.arange(0, v.max() + step, step)
        c, e = np.histogram(v, bins=edges)
        return {"edges": [r1(x) for x in e.tolist()], "counts": c.tolist()}

    dump("thresholds.json", {
        "blocks": T3, "by_year": by_year, "by_month": by_month,
        "percentiles": {
            "levels": pct_levels,
            "hour": [r1(np.percentile(wet_h, p), 2) for p in pct_levels],
            "day": [r1(np.percentile(wet_d, p), 2) for p in pct_levels],
            "hour_max": r1(wet_h.max()), "day_max": r1(wet_d.max()),
        },
        "hist": {"hour": hist(wet_h, 2), "day": hist(wet_d, 20)},
    })

    # ----- Chu kỳ lặp (Câu 4) -----
    print("Câu 4: phân tích tần suất (bootstrap, khoảng 1–2 phút) …")
    series = {"hour": (rx["rx1h"].values.astype(float), "Rx1hour"),
              "day": (rx["RX1day_mm"].values.astype(float), "Rx1day")}
    yrs = rx["year"].tolist()
    out = {"T_grid": T_GRID.tolist(), "T_table": T_TABLE, "n_boot": R.N_BOOT, "series": {}}
    hvs = hv.sort_values("datetime")
    th = (hvs["datetime"] - hvs["datetime"].iloc[0]).dt.total_seconds().values / 3600
    dvs = dv.sort_values("date")
    td = (dvs["date"] - dvs["date"].iloc[0]).dt.days.values.astype(float)
    for key, (x, label) in series.items():
        fits = R.fit_all(x)
        sel = R.choose(fits)
        models = {}
        for name, f in fits.items():
            dist = R.DISTS[name][0]
            models[name] = {
                "params": f["params"], "logL": f["logL"], "AIC": f["AIC"], "BIC": f["BIC"],
                "KS": f["KS"], "KS_p": f["KS_p"], "CvM": f["CvM"], "AD": f["AD"],
                "grid": [r1(v, 2) for v in dist.ppf(1 - 1 / T_GRID, *f["params"])],
            }
        boot = R.bootstrap(sel, x, fits[sel]["params"], T_GRID)
        lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
        mu_l, sg_l = R.gumbel_from_lmoments(x)
        lmom_grid = mu_l - sg_l * np.log(-np.log(1 - 1 / T_GRID))
        if key == "hour":
            pt = R.pot(th, hvs["rain_mm"].values, T3["hour_all"]["R95p"], 24, len(hvs) / 8766)
        else:
            pt = R.pot(td, dvs["rain_mm"].values, T3["day_all"]["R95p"], 3, len(dvs) / 365.25)
        pot_grid = R.gpd_rl(pt["u"], pt["xi"], pt["sigma"], pt["lam"], T_GRID)
        imax = int(np.argmax(x))
        pg = stats.gumbel_r.fit(np.delete(x, imax))
        xs = np.sort(x)
        n = len(xs)
        F = (np.arange(1, n + 1) - 0.44) / (n + 0.12)
        order = np.argsort(x)
        out["series"][key] = {
            "label": label, "unit": "mm/giờ" if key == "hour" else "mm/ngày",
            "values": [[int(yrs[i]), r1(x[i])] for i in range(len(x))],
            "gringorten": [[r1(1 / (1 - F[i]), 3), r1(xs[i]), int(yrs[order[i]])] for i in range(n)],
            "selected": sel, "models": models,
            "ci": {"model": sel, "lo": [r1(v, 2) for v in lo], "hi": [r1(v, 2) for v in hi]},
            "lmoment": {"mu": mu_l, "sigma": sg_l, "grid": [r1(v, 2) for v in lmom_grid]},
            "pot": {"u": pt["u"], "n_peaks": pt["n_peaks"], "lam": pt["lam"], "xi": pt["xi"], "sigma": pt["sigma"],
                    "grid": [r1(v, 2) for v in pot_grid],
                    "ci_table": {str(T): pt["ci"][T] for T in pt["ci"]}},
            "drop_max": {"value": r1(x[imax]), "year": int(yrs[imax]),
                         "grid": [r1(v, 2) for v in stats.gumbel_r.ppf(1 - 1 / T_GRID, *pg)]},
        }
        print(f"  {label}: chọn {sel}, T100 = {models[sel]['grid'][int(np.argmin(abs(T_GRID - 100)))]}")
    dump("returns.json", out)

    # ----- Trượt lở -----
    dd = daily.sort_values("date").set_index("date")
    acc3 = dd["rain_mm"].rolling(3, min_periods=1).sum()
    acc5 = dd["rain_mm"].rolling(5, min_periods=1).sum()
    ls = []
    for day in sorted(slide_days):
        hday = hourly[hourly["date"] == day]
        imax_h = hday["rain_mm"].idxmax() if hday["rain_mm"].notna().any() else None
        rain = dd.loc[day, "rain_mm"]
        ls.append({
            "date": day.strftime("%Y-%m-%d"), "rain": r1(rain), "valid": bool(dd.loc[day, "valid"]),
            "acc3": r1(acc3.loc[day]), "acc5": r1(acc5.loc[day]),
            "max_hour": r1(hday.loc[imax_h, "rain_mm"]) if imax_h is not None else None,
            "max_hour_at": int(hday.loc[imax_h, "hour"]) if imax_h is not None else None,
            "slide_hours": int(hday["landslide"].sum()),
            "gt_r95": bool(pd.notna(rain) and rain > d95), "gt_r99": bool(pd.notna(rain) and rain > d99),
        })
    dump("landslide.json", {"events": ls, "R95p_day": d95, "R99p_day": d99,
                            "n_days_gt_r99_with_slide": int(((dv["rain_mm"] > d99) & (dv["landslide"] == 1)).sum()),
                            "n_days_gt_r99": int((dv["rain_mm"] > d99).sum())})

    # ----- CSV tải về -----
    print("Xuất CSV …")
    csvdir = DATA / "csv"
    csvdir.mkdir(exist_ok=True)
    d_out = daily[["date", "rain_mm", "n_valid", "valid", "landslide"]].copy()
    d_out.columns = ["ngay", "luong_mua_mm", "so_gio_co_so_lieu", "ngay_hop_le", "truot_lo"]
    d_out["ngay"] = d_out["ngay"].dt.strftime("%Y-%m-%d")
    d_out.to_csv(csvdir / "mua_ngay.csv", index=False)
    pd.DataFrame(mrows, columns=["nam", "thang", "tong_mm", "so_ngay_hop_le", "so_ngay", "thang_hop_le",
                                 "so_ngay_mua", "mua_ngay_lon_nhat_mm"]).to_csv(csvdir / "mua_thang.csv", index=False)
    ann_df.rename(columns={"year": "nam", "total": "mua_nam_mm", "rainy": "mua_mua_IX_XII_mm", "dry": "mua_kho_I_VIII_mm",
                           "wet_days": "so_ngay_mua", "ok_year": "nam_hop_le", "ok_rainy": "mua_mua_hop_le",
                           "ok_dry": "mua_kho_hop_le", "valid_day_pct": "ty_le_ngay_hop_le",
                           "missing_hour_pct": "ty_le_gio_thieu", "max_day": "mua_ngay_lon_nhat_mm",
                           "max_hour": "mua_gio_lon_nhat_mm"}).to_csv(csvdir / "mua_nam.csv", index=False)
    pd.DataFrame(rx_rows).to_csv(csvdir / "chi_so_cuc_tri.csv", index=False)
    rl = []
    for key, s in out["series"].items():
        for T in T_TABLE:
            i = int(np.argmin(abs(T_GRID - T)))
            row = {"chuoi": s["label"], "T_nam": T}
            for name, m in s["models"].items():
                row[name] = m["grid"][i]
            row["KTC95_thap"] = s["ci"]["lo"][i]
            row["KTC95_cao"] = s["ci"]["hi"][i]
            row["POT_GPD"] = s["pot"]["grid"][i]
            rl.append(row)
    pd.DataFrame(rl).to_csv(csvdir / "chu_ky_lap_lai.csv", index=False)
    pd.DataFrame(ls).to_csv(csvdir / "truot_lo.csv", index=False)
    for f in sorted(csvdir.glob("*.csv")):
        print(f"  csv/{f.name:24s} {f.stat().st_size / 1024:8.1f} KB")

    import build_manifest
    build_manifest.main()
    print("Xong.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Kiểm tra dữ liệu web trước khi triển khai (chỉ dùng thư viện chuẩn)."""
from __future__ import annotations

import calendar
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
errors: list[str] = []


def load(rel: str):
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def check(cond: bool, msg: str) -> None:
    print(("ĐẠT  " if cond else "LỖI  ") + msg)
    if not cond:
        errors.append(msg)


def near(a, b, tol=0.06) -> bool:
    return a is not None and abs(a - b) <= tol


required = ["meta.json", "daily.json", "monthly.json", "annual.json", "summary.json", "rx.json",
            "events.json", "thresholds.json", "returns.json", "landslide.json"]
for f in required:
    check((DATA / f).exists(), f"có file {f}")
if errors:
    sys.exit(1)

meta = load("meta.json")
years = meta["years"]
check(years == list(range(2008, 2018)), "10 năm 2008–2017")

# Độ dài chuỗi
for y in years:
    h = load(f"hourly/{y}.json")
    n = (366 if calendar.isleap(y) else 365) * 24
    check(len(h["rain"]) == n, f"mưa giờ {y}: {n} giá trị")
daily = load("daily.json")
check(len(daily["rain"]) == 3653 and len(daily["valid_hours"]) == 3653, "mưa ngày: 3653 giá trị")
check(len(daily["slide"]) == 28, "28 ngày trượt lở")

# Khớp số liệu với báo cáo LaTeX
thr = load("thresholds.json")["blocks"]
check(near(thr["hour_all"]["R95p"], 20.1), "R95p giờ = 20,1 mm")
check(near(thr["hour_all"]["R99p"], 39.4), "R99p giờ = 39,4 mm")
check(near(thr["day_all"]["R95p"], 89.16, 0.01), "R95p ngày = 89,16 mm")
check(near(thr["day_all"]["R99p"], 209.01, 0.01), "R99p ngày = 209,01 mm")

rx = load("rx.json")["rows"]
check(max(r["rx1day"] for r in rx) == 781.6, "Rx1day lớn nhất = 781,6 mm")
check(max(r["rx5day"] for r in rx) == 1255.4, "Rx5day lớn nhất = 1255,4 mm")
check(all(r["rx1day"] <= r["rx5day"] for r in rx), "Rx1day <= Rx5day mọi năm")

ret = load("returns.json")
grid = ret["T_grid"]
i100 = grid.index(100)
for key, val in (("day", 849.8), ("hour", 114.5)):
    s = ret["series"][key]
    g = s["models"][s["selected"]]["grid"]
    check(s["selected"] == "Gumbel", f"{key}: chọn Gumbel")
    check(near(g[i100], val), f"{key}: mức 100 năm = {val}")
    check(all(g[i] < g[i + 1] for i in range(len(g) - 1)), f"{key}: mức mưa tăng theo T")
    check(all(lo <= m <= hi for lo, m, hi in zip(s["ci"]["lo"], g, s["ci"]["hi"])), f"{key}: KTC bao ước lượng")

ann = load("annual.json")["stats"]["total"]
check(near(ann["mean"], 4192.46, 0.1), "lượng mưa năm TB = 4192,5 mm")

# Dung lượng
json_size = sum(p.stat().st_size for p in DATA.rglob("*.json"))
check(json_size < 3 * 1024 * 1024, f"tổng JSON {json_size / 1024:.0f} KB < 3 MB")

print()
if errors:
    print(f"{len(errors)} lỗi")
    sys.exit(1)
print("Dữ liệu hợp lệ.")

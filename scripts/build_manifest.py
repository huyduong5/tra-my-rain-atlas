#!/usr/bin/env python3
"""Ghi data/files.json: danh sách file tải về kèm mô tả và dung lượng (dùng cho trang Tải dữ liệu)."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

DESCRIPTIONS = {
    "raw/Hourly_rain_Tra_My_2008_2017.csv": ("Số liệu gốc mưa giờ", "Cột Ngay, Gio (1–24), Luong mua (mm), cờ trượt lở; 87 672 dòng"),
    "csv/mua_ngay.csv": ("Mưa ngày", "Tổng mưa ngày, số giờ có số liệu, cờ ngày hợp lệ, cờ trượt lở"),
    "csv/mua_thang.csv": ("Mưa tháng", "Tổng mưa tháng, số ngày hợp lệ, cờ tháng hợp lệ, số ngày mưa"),
    "csv/mua_nam.csv": ("Mưa năm và mùa", "Mưa năm, mùa mưa IX–XII, mùa khô I–VIII, số ngày mưa, cờ hợp lệ"),
    "csv/chi_so_cuc_tri.csv": ("Chỉ số cực trị", "Rx1day, Rx5day, Rx1hour theo năm, ngày xảy ra, cờ trượt lở"),
    "csv/chu_ky_lap_lai.csv": ("Mưa theo chu kỳ lặp lại", "T = 2–500 năm cho 5 phân bố, POT và khoảng tin cậy 95%"),
    "csv/truot_lo.csv": ("Ngày có trượt lở", "Mưa ngày, tích lũy 3 và 5 ngày, giờ mưa lớn nhất"),
    "returns.json": ("Kết quả phân tích tần suất (JSON)", "Tham số, chỉ tiêu phù hợp và lưới mức mưa theo T"),
    "thresholds.json": ("Ngưỡng R95p/R99p (JSON)", "Ngưỡng, số lần vượt theo năm/tháng, phân vị 1–99"),
    "summary.json": ("Thống kê mô tả (JSON)", "Thống kê mưa giờ, ngày theo mùa, chu trình ngày"),
}


def main() -> None:
    files = []
    for rel, (title, desc) in DESCRIPTIONS.items():
        p = DATA / rel
        if p.exists():
            files.append({"path": f"data/{rel}", "title": title, "desc": desc, "size": p.stat().st_size,
                          "type": p.suffix.lstrip(".").upper()})
    files.append({"path": "data/hourly/", "title": "Mưa giờ theo năm (JSON)", "type": "JSON",
                  "desc": "10 file hourly/2008.json … 2017.json, mỗi file là mảng lượng mưa từng giờ", "size":
                  sum(p.stat().st_size for p in (DATA / "hourly").glob("*.json"))})
    (DATA / "files.json").write_text(json.dumps({"files": files}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"data/files.json: {len(files)} mục")


if __name__ == "__main__":
    main()

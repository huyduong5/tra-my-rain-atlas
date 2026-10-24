// Sơ đồ trang và quy ước URL hash: #/<duong-dan>?thamso=giatri
// Tham số dùng chung: ngay=YYYY-MM-DD, nam=YYYY, chuoi=gio|ngay, mohinh=..., T=số năm
export const ROUTES = [
  { path: "", title: "Tổng quan", module: "overview" },
  { path: "tra-cuu", title: "Tra cứu", module: "lookup" },
  { path: "thong-ke", title: "Thống kê", module: "stats", badge: "Câu 1" },
  { path: "cuc-tri", title: "Cực trị", module: "extremes", badge: "Câu 2" },
  { path: "nguong", title: "Ngưỡng R95p/R99p", module: "thresholds", badge: "Câu 3" },
  { path: "chu-ky", title: "Chu kỳ lặp", module: "returns", badge: "Câu 4" },
  { path: "truot-lo", title: "Trượt lở", module: "landslide" },
  { path: "tai-du-lieu", title: "Tải dữ liệu", module: "downloads" },
  { path: "phuong-phap", title: "Phương pháp", module: "methods" },
];

export const SITE = {
  name: "Trà My Rain Atlas",
  station: "Trạm Trà My",
  repo: "https://github.com/OWNER/tra-my-rain-atlas",
};

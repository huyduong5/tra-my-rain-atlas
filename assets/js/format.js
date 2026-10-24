// Định dạng số và ngày kiểu Việt Nam
export const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
export const MONTH_NAMES = ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
  "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"];

export function fmt(x, nd = 1) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return Number(x).toLocaleString("vi-VN", { minimumFractionDigits: nd, maximumFractionDigits: nd });
}

export const fmtInt = (x) => fmt(x, 0);

/** "2017-11-05" -> "05/11/2017" */
export function fmtDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/** "2017-11-05" -> "05/11" */
export const fmtDM = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "—");

export function toISO(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseISO(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** Mốc thời gian (ms, UTC) của 00:00 ngày ISO — dùng cho trục thời gian */
export const utcMs = (iso) => parseISO(iso).getTime();

export function addDays(iso, n) {
  const t = parseISO(iso);
  t.setUTCDate(t.getUTCDate() + n);
  return toISO(t);
}

/** Số ngày giữa hai ngày ISO (b - a) */
export function dayDiff(a, b) {
  return Math.round((parseISO(b) - parseISO(a)) / 86400000);
}

export function isLeap(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

export const pct = (x, nd = 1) => `${fmt(x, nd)}%`;

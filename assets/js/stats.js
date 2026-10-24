// Thống kê phía trình duyệt — cùng công thức với pipeline Python
// (độ lệch chuẩn mẫu n-1, phân vị nội suy tuyến tính, độ lệch Fisher–Pearson hiệu chỉnh)

export function quantile(sorted, p) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export function describe(values) {
  const x = values.filter((v) => v !== null && v !== undefined && !Number.isNaN(v));
  const n = x.length;
  if (!n) return { n: 0 };
  const s = x.slice().sort((a, b) => a - b);
  const mean = x.reduce((a, b) => a + b, 0) / n;
  const m2 = x.reduce((a, b) => a + (b - mean) ** 2, 0);
  const std = n > 1 ? Math.sqrt(m2 / (n - 1)) : 0;
  let skew = null;
  if (n > 2 && std > 0) {
    const m3 = x.reduce((a, b) => a + ((b - mean) / std) ** 3, 0);
    skew = (n / ((n - 1) * (n - 2))) * m3;
  }
  return {
    n, mean, std, cv: mean ? (100 * std) / mean : null, median: quantile(s, 0.5),
    p25: quantile(s, 0.25), p75: quantile(s, 0.75), p90: quantile(s, 0.9),
    p95: quantile(s, 0.95), p99: quantile(s, 0.99), min: s[0], max: s[n - 1], skew, sum: mean * n,
  };
}

export function rainStats(values, big = [50, 100]) {
  const x = values.filter((v) => v !== null && v !== undefined);
  const d = describe(x);
  const wet = x.filter((v) => v >= 1);
  const dw = describe(wet);
  return {
    ...d, n_wet: wet.length, freq_wet: x.length ? (100 * wet.length) / x.length : null,
    mean_wet: dw.mean ?? null, median_wet: dw.median ?? null,
    n_big1: x.filter((v) => v > big[0]).length, n_big2: x.filter((v) => v > big[1]).length,
  };
}

/** Nội suy tuyến tính y(x) trên mảng xs tăng dần */
export function interp(x, xs, ys) {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let i = 1;
  while (xs[i] < x) i++;
  const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return ys[i - 1] + t * (ys[i] - ys[i - 1]);
}

/** Nội suy theo log(T): mức mưa ứng với chu kỳ T */
export function levelAt(T, grid, values) {
  return interp(Math.log(T), grid.map(Math.log), values);
}

/** Ngược lại: chu kỳ T ứng với lượng mưa v (giá trị tăng theo T) */
export function periodOf(v, grid, values) {
  if (v < values[0] || v > values[values.length - 1]) return null;
  return Math.exp(interp(v, values, grid.map(Math.log)));
}

/** Năm × giá trị quan trắc: 5 điểm cho boxplot [min, Q1, median, Q3, max] */
export function boxStats(values) {
  const s = values.filter((v) => v !== null).sort((a, b) => a - b);
  if (!s.length) return [null, null, null, null, null];
  return [s[0], quantile(s, 0.25), quantile(s, 0.5), quantile(s, 0.75), s[s.length - 1]];
}

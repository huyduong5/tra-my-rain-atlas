// Tải dữ liệu JSON có bộ nhớ đệm; mưa giờ tải theo từng năm khi cần
import { addDays, dayDiff } from "./format.js";

const cache = new Map();

export function getJSON(name) {
  if (!cache.has(name)) {
    const p = fetch(`data/${name}`).then((r) => {
      if (!r.ok) throw new Error(`Không tải được data/${name} (HTTP ${r.status})`);
      return r.json();
    });
    p.catch(() => cache.delete(name));
    cache.set(name, p);
  }
  return cache.get(name);
}

export const load = (...names) => Promise.all(names.map((n) => getJSON(`${n}.json`)));
export const hourly = (year) => getJSON(`hourly/${year}.json`);

/** Mưa ngày theo ngày ISO; null nếu ngày không hợp lệ hoặc ngoài chuỗi */
export function dailyValue(daily, iso) {
  const i = dayDiff(daily.start, iso);
  return i >= 0 && i < daily.rain.length ? daily.rain[i] : undefined;
}

export function dailyIndexToISO(daily, i) {
  return addDays(daily.start, i);
}

/** Lấy 24 giá trị mưa giờ của một ngày */
export async function hoursOfDay(iso) {
  const y = Number(iso.slice(0, 4));
  const h = await hourly(y);
  const i = dayDiff(h.start, iso);
  const rain = h.rain.slice(i * 24, i * 24 + 24);
  const slide = new Set(h.slide.filter((k) => k >= i * 24 && k < i * 24 + 24).map((k) => k - i * 24));
  return { rain, slide };
}

// Bọc ECharts: theme thống nhất, tự resize, giải phóng khi đổi trang
import { fmt } from "./format.js";

export const C = {
  sea: "#1b4b63", rain: "#3a7ca5", soft: "#9cc3d9", orange: "#c45c26",
  gold: "#b7862c", slide: "#7a1f1f", ink: "#0b1c24", muted: "#5a6f7a", green: "#2f6f4e", grey: "#6b7280",
};

const live = new Set();
let resizeBound = false;

function bindResize() {
  if (resizeBound) return;
  resizeBound = true;
  let t;
  window.addEventListener("resize", () => {
    clearTimeout(t);
    t = setTimeout(() => live.forEach((c) => c.resize()), 150);
  });
}

export function disposeAll() {
  live.forEach((c) => c.dispose());
  live.clear();
}

const base = {
  color: [C.sea, C.orange, C.rain, C.gold, C.green, C.slide],
  textStyle: { fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color: C.ink },
  grid: { left: 56, right: 24, top: 40, bottom: 48, containLabel: true },
  tooltip: {
    trigger: "axis", confine: true,
    valueFormatter: (v) => (v === null || v === undefined ? "—" : fmt(v, 1)),
  },
  toolbox: {
    right: 6, top: 0, itemSize: 13,
    feature: { saveAsImage: { title: "Lưu ảnh PNG", pixelRatio: 2, backgroundColor: "#fff" } },
  },
  animationDuration: 400,
};

function merge(a, b) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b)) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && a[k] && typeof a[k] === "object" && !Array.isArray(a[k])
      ? merge(a[k], v) : v;
  }
  return out;
}

const vnAxisLabel = (v) => Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 2 });

/** Trục số (value/log) hiển thị số kiểu Việt Nam nếu chưa có formatter riêng */
function localizeAxes(option) {
  for (const key of ["xAxis", "yAxis"]) {
    const axes = option[key];
    if (!axes) continue;
    for (const ax of Array.isArray(axes) ? axes : [axes]) {
      if ((ax.type === "value" || ax.type === "log") && !(ax.axisLabel && ax.axisLabel.formatter)) {
        ax.axisLabel = { ...(ax.axisLabel || {}), formatter: vnAxisLabel };
      }
    }
  }
  return option;
}

/** Tạo biểu đồ trong phần tử el với option (được trộn với theme chung) */
export function chart(el, option, { label } = {}) {
  bindResize();
  const c = window.echarts.init(el, null, { renderer: "canvas" });
  c.setOption(localizeAxes(merge(base, option)));
  const set = c.setOption.bind(c);
  c.setOption = (opt, ...rest) => set(localizeAxes(opt), ...rest);
  if (label) {
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", label);
  }
  live.add(c);
  return c;
}

export const axisName = (name, extra = {}) => ({ name, nameLocation: "middle", nameGap: 36, ...extra });

export function markLines(lines) {
  return {
    symbol: "none", silent: true,
    data: lines.map(([v, color, text, axis = "yAxis"]) => ({
      [axis]: v,
      lineStyle: { color, type: "dashed", width: 1.6 },
      label: { formatter: text, color, position: "insideEndTop", fontWeight: 600 },
    })),
  };
}

export const zoom = (orient = "x") => [
  { type: "inside", [`${orient}AxisIndex`]: 0 },
  { type: "slider", [`${orient}AxisIndex`]: 0, height: 18, bottom: 6 },
];

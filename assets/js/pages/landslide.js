import { load } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, notice } from "../components.js";
import { chart, C, axisName, markLines } from "../charts.js";
import { fmt, fmtDate, addDays } from "../format.js";
import { go } from "../router.js";

export async function render(host) {
  const [ls, daily] = await load("landslide", "daily");
  const ev = ls.events;
  const R95 = ls.R95p_day;
  const R99 = ls.R99p_day;
  const slideSet = new Set(daily.slide);

  // Lượng mưa tích lũy 5 ngày cho mọi ngày (để so sánh ngày có và không có trượt lở)
  const acc5 = daily.rain.map((_, i) => {
    let s = 0;
    let n = 0;
    for (let k = Math.max(0, i - 4); k <= i; k++) if (daily.rain[k] !== null) { s += daily.rain[k]; n++; }
    return n ? s : null;
  });
  const others = [];
  const slides = [];
  daily.rain.forEach((v, i) => {
    if (v === null || acc5[i] === null) return;
    (slideSet.has(i) ? slides : others).push([acc5[i], v, addDays(daily.start, i)]);
  });
  const byYear = {};
  ev.forEach((e) => { byYear[e.date.slice(0, 4)] = (byYear[e.date.slice(0, 4)] || 0) + 1; });
  const byMonth = {};
  ev.forEach((e) => { byMonth[+e.date.slice(5, 7)] = (byMonth[+e.date.slice(5, 7)] || 0) + 1; });

  const statCards = h("div", { class: "stats" }, [
    ["Số ngày có trượt lở", ev.length, "ngày", `${Object.keys(byYear).length} năm có ghi nhận; tất cả trong tháng IX–XII`, "slide"],
    ["Mưa ngày vượt R95p", `${ev.filter((e) => e.gt_r95).length}/${ev.length}`, "ngày", `R95p = ${fmt(R95, 1)} mm`, "orange"],
    ["Ngày mưa > R99p có trượt lở", `${ls.n_days_gt_r99_with_slide}/${ls.n_days_gt_r99}`, "ngày", `R99p = ${fmt(R99, 1)} mm`, "orange"],
    ["Mưa ngày TB khi trượt lở", fmt(ev.reduce((a, e) => a + (e.rain || 0), 0) / ev.length, 1), "mm", `tích lũy 5 ngày TB ${fmt(ev.reduce((a, e) => a + (e.acc5 || 0), 0) / ev.length, 0)} mm`, ""],
  ].map(([l, v, u, n, tone]) => h("div", { class: `stat ${tone}` }, h("div", { class: "label" }, l),
    h("div", { class: "value" }, v, h("span", { class: "unit" }, u)), h("div", { class: "note" }, n))));

  const scCard = card("Mưa ngày và mưa tích lũy 5 ngày", { sub: "Điểm xám: mọi ngày hợp lệ; điểm đỏ: ngày có trượt lở. Vạch ngang: R95p, R99p của mưa ngày." });
  const scEl = chartBox("tall");
  scCard.body.append(scEl, caption("Hầu hết ngày trượt lở nằm phía trên ngưỡng R95p và có lượng mưa 5 ngày trên khoảng 200 mm: mưa lớn kéo dài nhiều ngày là yếu tố kích hoạt chính."));
  const yCard = card("Số ngày trượt lở theo năm và tháng", {});
  const yEl = chartBox();
  yCard.body.append(yEl);

  const tCard = card("Danh sách ngày có trượt lở", { sub: "Bấm vào dòng để xem mưa từng giờ của ngày đó" });
  tCard.body.append(dataTable([
    { key: "date", label: "Ngày", align: "left", fmt: (v) => fmtDate(v) },
    { key: "rain", label: "Mưa ngày (mm)", fmt: (v) => fmt(v, 1) },
    { key: "acc3", label: "Tích lũy 3 ngày", fmt: (v) => fmt(v, 1) },
    { key: "acc5", label: "Tích lũy 5 ngày", fmt: (v) => fmt(v, 1) },
    { key: "max_hour", label: "Giờ mưa lớn nhất", fmt: (v, r) => (v === null ? "—" : `${fmt(v, 1)} (lúc ${r.max_hour_at} giờ)`) },
    { key: "slide_hours", label: "Số giờ trượt lở" },
    { key: "gt_r95", label: "Mức", fmt: (v, r) => (r.gt_r99 ? '<span class="flag slide">> R99p</span>' : v ? '<span class="flag warn">> R95p</span>' : "") },
  ], ev, { csvName: "truot_lo.csv", search: true, onRowClick: (r) => go("tra-cuu", { ngay: r.date }) }));

  host.replaceChildren(
    pageHead("Mở rộng", "Mưa lớn và trượt lở đất",
      "Bộ số liệu có cờ ghi nhận trượt lở theo giờ. Trang này đối chiếu các ngày có trượt lở với lượng mưa ngày, mưa tích lũy nhiều ngày và các ngưỡng R95p/R99p, gợi ý mức mưa có nguy cơ gây trượt lở tại khu vực Trà My."),
    statCards,
    h("div", { class: "grid grid-2" }, scCard.root, yCard.root),
    tCard.root,
    notice("Kết quả mang tính thống kê mô tả trên một trạm; ngưỡng cảnh báo trượt lở thực tế cần xét thêm địa chất, độ dốc và độ ẩm đất."));

  const sc = chart(scEl, {
    tooltip: { trigger: "item", formatter: (p) => `${fmtDate(p.data[2])}<br>Mưa ngày: ${fmt(p.data[1], 1)} mm<br>Tích lũy 5 ngày: ${fmt(p.data[0], 1)} mm` },
    legend: { top: 0, left: 0 },
    grid: { top: 40 },
    xAxis: { type: "value", ...axisName("Mưa tích lũy 5 ngày (mm)") },
    yAxis: { type: "value", ...axisName("Mưa ngày (mm)", { nameGap: 48 }) },
    series: [
      { name: "Ngày không trượt lở", type: "scatter", data: others, symbolSize: 4, itemStyle: { color: "rgba(90,111,122,.35)" }, large: true },
      { name: "Ngày có trượt lở", type: "scatter", data: slides, symbolSize: 10, itemStyle: { color: C.slide, borderColor: "#fff", borderWidth: 1 },
        markLine: markLines([[R95, C.gold, `R95p ${fmt(R95, 1)}`], [R99, C.orange, `R99p ${fmt(R99, 1)}`]]) },
    ],
  }, { label: "Biểu đồ phân tán mưa ngày và mưa tích lũy 5 ngày" });
  sc.on("click", (p) => p.data && go("tra-cuu", { ngay: p.data[2] }));

  const years = Array.from({ length: 10 }, (_, k) => String(2008 + k));
  chart(yEl, {
    tooltip: { trigger: "axis" },
    grid: [{ left: 50, right: 20, top: 30, height: "32%" }, { left: 50, right: 20, top: "62%", height: "28%" }],
    xAxis: [{ type: "category", data: years, gridIndex: 0 }, { type: "category", data: ["IX", "X", "XI", "XII"], gridIndex: 1 }],
    yAxis: [{ type: "value", name: "Theo năm", gridIndex: 0, minInterval: 1 }, { type: "value", name: "Theo tháng", gridIndex: 1, minInterval: 1 }],
    series: [
      { type: "bar", data: years.map((y) => byYear[y] || 0), itemStyle: { color: C.slide }, label: { show: true, position: "top" } },
      { type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: [9, 10, 11, 12].map((m) => byMonth[m] || 0), itemStyle: { color: C.orange }, label: { show: true, position: "top" } },
    ],
  }, { label: "Số ngày trượt lở theo năm và tháng" });
}

import { load, hoursOfDay } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, downloadText, toCSV, shareButton, notice, term } from "../components.js";
import { chart, C, markLines, zoom, axisName } from "../charts.js";
import { fmt, fmtDate, addDays, dayDiff, utcMs } from "../format.js";
import { setParams } from "../router.js";
import { interp } from "../stats.js";

const FIRST = "2008-01-01";
const LAST = "2017-12-31";

export async function render(host, params, alive) {
  const [daily, thr, summary] = await load("daily", "thresholds", "summary");
  const slideSet = new Set(daily.slide);
  const B = thr.blocks;
  let day = /^\d{4}-\d{2}-\d{2}$/.test(params.ngay || "") && params.ngay >= FIRST && params.ngay <= LAST ? params.ngay : "2017-11-05";

  // ----- Thanh công cụ -----
  const dateInput = h("input", { type: "date", min: FIRST, max: LAST, value: day, "aria-label": "Chọn ngày" });
  const topSel = h("select", { "aria-label": "Ngày mưa lớn nhất" },
    h("option", { value: "" }, "— 10 ngày mưa lớn nhất —"),
    summary.top_days.map(([d, v]) => h("option", { value: d }, `${fmtDate(d)} · ${fmt(v, 1)} mm`)));
  const slideSel = h("select", { "aria-label": "Ngày có trượt lở" },
    h("option", { value: "" }, "— Ngày có trượt lở —"),
    daily.slide.map((i) => { const d = addDays(daily.start, i); return h("option", { value: d }, fmtDate(d)); }));
  const toolbar = h("div", { class: "toolbar" },
    h("label", { class: "field" }, "Ngày tra cứu", dateInput),
    h("div", { class: "day-nav" },
      h("button", { class: "btn", type: "button", onclick: () => select(addDays(day, -1)) }, "← Ngày trước"),
      h("button", { class: "btn", type: "button", onclick: () => select(addDays(day, 1)) }, "Ngày sau →")),
    h("label", { class: "field" }, "Chọn nhanh", topSel),
    h("label", { class: "field" }, "Sự kiện trượt lở", slideSel),
    shareButton());
  dateInput.addEventListener("change", () => dateInput.value && select(dateInput.value));
  topSel.addEventListener("change", () => topSel.value && select(topSel.value));
  slideSel.addEventListener("change", () => slideSel.value && select(slideSel.value));

  // ----- Thẻ ngày được chọn -----
  const dayCard = card("", {});
  const summaryBox = h("div", {});
  const hourEl = chartBox();
  const hourTable = h("div", {});
  dayCard.body.append(summaryBox, hourEl, h("div", { style: "margin-top:.75rem" }, hourTable));

  // ----- Heatmap 10 năm -----
  const heatCard = card("Lịch mưa ngày 2008–2017", {
    sub: "Mỗi ô là một ngày; màu càng đậm mưa càng lớn, ô xám là ngày thiếu số liệu. Bấm vào ô để xem ngày đó.",
  });
  const heatEl = chartBox("tall");
  heatCard.body.append(heatEl);

  // ----- Chuỗi mưa ngày -----
  const seriesCard = card("Chuỗi mưa ngày", {
    sub: `Kéo thanh trượt bên dưới để phóng to. Vạch: R95p = ${fmt(B.day_all.R95p, 1)} mm, R99p = ${fmt(B.day_all.R99p, 1)} mm. Bấm vào cột để chọn ngày.`,
    actions: [h("button", { class: "btn small", type: "button", onclick: exportWindow }, "Tải CSV 60 ngày quanh ngày chọn")],
  });
  const seriesEl = chartBox("tall");
  seriesCard.body.append(seriesEl);

  host.replaceChildren(
    pageHead("Tra cứu", "Tra cứu lượng mưa theo ngày và giờ",
      `Chọn một ngày bất kỳ từ ${fmtDate(FIRST)} đến ${fmtDate(LAST)} để xem lượng mưa từng giờ, so sánh với ngưỡng ${term("R95p/R99p", "Phân vị 95% và 99% của lượng mưa các giờ (ngày) có mưa ≥ 1 mm, giai đoạn 2008–2017")} và vị trí của ngày đó trong toàn chuỗi. Đường link trên thanh địa chỉ luôn trỏ tới đúng ngày đang xem.`),
    toolbar, dayCard.root, heatCard.root, seriesCard.root);

  // Heatmap: trục x = ngày trong năm, trục y = năm
  const years = [];
  for (let y = 2008; y <= 2017; y++) years.push(y);
  const cells = [];
  daily.rain.forEach((v, i) => {
    const iso = addDays(daily.start, i);
    const y = +iso.slice(0, 4);
    const doy = dayDiff(`${y}-01-01`, iso);
    cells.push([doy, years.indexOf(y), v === null ? -1 : v, iso]);
  });
  const monthStarts = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  const heat = chart(heatEl, {
    tooltip: {
      trigger: "item",
      formatter: (p) => `${fmtDate(p.data[3])}<br>${p.data[2] < 0 ? "Thiếu số liệu" : `${fmt(p.data[2], 1)} mm`}${slideSet.has(dayDiff(daily.start, p.data[3])) ? "<br><b>Có trượt lở</b>" : ""}`,
    },
    grid: { left: 50, right: 20, top: 20, bottom: 70 },
    xAxis: {
      type: "category", data: Array.from({ length: 366 }, (_, i) => i),
      axisLabel: { interval: (i) => monthStarts.includes(i), formatter: (i) => `T${monthStarts.indexOf(+i) + 1}` },
      axisTick: { show: false }, splitArea: { show: false },
    },
    yAxis: { type: "category", data: years.map(String), inverse: true },
    visualMap: {
      type: "piecewise", dimension: 2, orient: "horizontal", left: "center", bottom: 0, itemWidth: 14,
      pieces: [
        { value: -1, label: "Thiếu", color: "#d5d9dc" },
        { min: 0, max: 0.99, label: "< 1", color: "#f2f6f8" },
        { min: 1, max: 9.99, label: "1–10", color: "#cfe1ec" },
        { min: 10, max: 49.99, label: "10–50", color: "#8fb9d3" },
        { min: 50, max: 99.99, label: "50–100", color: "#3a7ca5" },
        { min: 100, max: 199.99, label: "100–200", color: "#1b4b63" },
        { min: 200, label: "≥ 200 mm", color: "#c45c26" },
      ],
    },
    series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: "#fff", borderWidth: 0.3 }, progressive: 0 }],
  }, { label: "Lịch nhiệt mưa ngày 10 năm" });
  heat.on("click", (p) => p.data && select(p.data[3]));

  // Chuỗi mưa ngày toàn giai đoạn
  const dailyData = daily.rain.map((v, i) => [utcMs(addDays(daily.start, i)), v]);
  const series = chart(seriesEl, {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { bottom: 70 },
    xAxis: { type: "time", axisLabel: { formatter: "{dd}/{MM}/{yyyy}" } },
    yAxis: { type: "value", name: "mm/ngày" },
    dataZoom: zoom("x"),
    series: [{
      name: "Mưa ngày", type: "bar", data: dailyData, itemStyle: { color: C.rain }, large: true,
      markLine: markLines([[B.day_all.R95p, C.gold, "R95p"], [B.day_all.R99p, C.slide, "R99p"]]),
    }],
  }, { label: "Chuỗi mưa ngày 2008–2017" });
  series.on("click", (p) => p.value && select(new Date(p.value[0]).toISOString().slice(0, 10)));

  let hourChart = null;
  async function select(d) {
    if (d < FIRST || d > LAST) return;
    day = d;
    dateInput.value = d;
    setParams({ ngay: d });
    await showDay();
  }

  function percentileOf(v, arr) {
    const lv = thr.percentiles.levels;
    if (v < arr[0]) return "< 1";
    if (v > arr[arr.length - 1]) return "> 99,9";
    return fmt(interp(v, arr, lv), 1);
  }

  async function showDay() {
    const i = dayDiff(daily.start, day);
    const dv = daily.rain[i];
    const { rain, slide } = await hoursOfDay(day);
    if (alive && !alive()) return;
    const nValid = daily.valid_hours[i];
    const wetHours = rain.filter((v) => v !== null && v >= 1).length;
    const maxH = Math.max(...rain.map((v) => v ?? -1));
    const level = dv === null ? "" : dv > B.day_all.R99p ? "cực kỳ lớn (> R99p)" : dv > B.day_all.R95p ? "rất lớn (> R95p)" : dv >= 1 ? "có mưa" : "không mưa (< 1 mm)";
    summaryBox.replaceChildren(
      h("div", { class: "day-nav" }, h("span", { class: "day-title" }, `Ngày ${fmtDate(day)}`),
        slideSet.has(i) ? h("span", { class: "flag slide" }, "Có trượt lở") : null,
        dv !== null && dv > B.day_all.R95p ? h("span", { class: "flag warn" }, level) : null),
      dv === null
        ? notice(`Ngày này không đủ số liệu (${nValid}/24 giờ có số liệu) nên không tính lượng mưa ngày.`, "warn")
        : h("div", { class: "stats" },
          h("div", { class: "stat" }, h("div", { class: "label" }, "Lượng mưa ngày"), h("div", { class: "value" }, fmt(dv, 1), h("span", { class: "unit" }, "mm")),
            h("div", { class: "note" }, dv >= 1 ? `Phân vị ${percentileOf(dv, thr.percentiles.day)} trong các ngày mưa` : "Không mưa")),
          h("div", { class: "stat orange" }, h("div", { class: "label" }, "Giờ mưa lớn nhất"), h("div", { class: "value" }, fmt(maxH, 1), h("span", { class: "unit" }, "mm")),
            h("div", { class: "note" }, `lúc ${rain.indexOf(maxH) + 1} giờ`)),
          h("div", { class: "stat" }, h("div", { class: "label" }, "Số giờ mưa ≥ 1 mm"), h("div", { class: "value" }, wetHours, h("span", { class: "unit" }, "giờ")),
            h("div", { class: "note" }, `${nValid}/24 giờ có số liệu`)),
          h("div", { class: "stat" }, h("div", { class: "label" }, "Đánh giá"), h("div", { class: "value", style: "font-size:1.05rem" }, level))));

    if (!hourChart) {
      hourChart = chart(hourEl, {
        tooltip: { trigger: "axis" },
        grid: { top: 56 },
        xAxis: { type: "category", data: Array.from({ length: 24 }, (_, k) => String(k + 1)), ...axisName("Giờ trong ngày") },
        yAxis: { type: "value", ...axisName("mm/giờ", { nameGap: 40 }) },
        series: [{ name: "Mưa giờ", type: "bar" }],
      }, { label: "Biểu đồ mưa 24 giờ của ngày chọn" });
    }
    hourChart.setOption({
      title: { text: `Mưa từng giờ ngày ${fmtDate(day)}`, left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600 } },
      yAxis: { max: (v) => Math.ceil(Math.max(v.max * 1.15, B.hour_all.R99p * 1.15) / 10) * 10 },
      series: [{
        data: rain.map((v, k) => ({ value: v, itemStyle: { color: slide.has(k) ? C.slide : v > B.hour_all.R95p ? C.orange : C.rain } })),
        markLine: markLines([[B.hour_all.R95p, C.gold, `R95p giờ ${fmt(B.hour_all.R95p, 1)}`], [B.hour_all.R99p, C.slide, `R99p giờ ${fmt(B.hour_all.R99p, 1)}`]]),
      }],
    });
    const rows = rain.map((v, k) => ({ gio: k + 1, mua: v, luyke: null, truotlo: slide.has(k) }));
    let acc = 0;
    rows.forEach((r) => { acc += r.mua || 0; r.luyke = acc; });
    hourTable.replaceChildren(dataTable([
      { key: "gio", label: "Giờ", align: "left", fmt: (v) => `${v}:00` },
      { key: "mua", label: "Mưa (mm)", fmt: (v) => (v === null ? "thiếu" : fmt(v, 1)) },
      { key: "luyke", label: "Lũy kế (mm)", fmt: (v) => fmt(v, 1) },
      { key: "truotlo", label: "Trượt lở", fmt: (v) => (v ? '<span class="flag slide">có</span>' : ""), csv: (r) => (r.truotlo ? 1 : 0) },
    ], rows, { csvName: `mua_gio_${day}.csv`, maxHeight: "320px" }));

    // Đưa chuỗi mưa ngày về khoảng ±60 ngày quanh ngày chọn
    series.dispatchAction({ type: "dataZoom", startValue: utcMs(addDays(day, -60)), endValue: utcMs(addDays(day, 60)) });
    series.setOption({ series: [{ markPoint: { symbol: "pin", symbolSize: 36, itemStyle: { color: C.orange }, data: [{ coord: [utcMs(day), dv ?? 0], value: "" }] } }] });
  }

  function exportWindow() {
    const rows = [];
    for (let k = -30; k <= 30; k++) {
      const d = addDays(day, k);
      const i = dayDiff(daily.start, d);
      if (i < 0 || i >= daily.rain.length) continue;
      rows.push({ ngay: d, mua: daily.rain[i], gio: daily.valid_hours[i], truotlo: slideSet.has(i) ? 1 : 0 });
    }
    downloadText(`mua_ngay_${addDays(day, -30)}_${addDays(day, 30)}.csv`, toCSV([
      { key: "ngay", label: "ngay" }, { key: "mua", label: "luong_mua_mm" }, { key: "gio", label: "so_gio_co_so_lieu" }, { key: "truotlo", label: "truot_lo" },
    ], rows));
  }

  await showDay();
}

import { load } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, term, notice } from "../components.js";
import { chart, C } from "../charts.js";
import { fmt, fmtDate, fmtDM, utcMs } from "../format.js";
import { setParams } from "../router.js";

export async function render(host, params) {
  const [rx, events, thr] = await load("rx", "events", "thresholds");
  const rows = rx.rows;
  let year = rows.some((r) => r.year === +params.nam) ? +params.nam : 2017;
  const S = rx.stats;
  const max1 = rows.reduce((a, b) => (b.rx1day > a.rx1day ? b : a));
  const max5 = rows.reduce((a, b) => (b.rx5day > a.rx5day ? b : a));
  const maxh = rows.reduce((a, b) => (b.rx1hour > a.rx1hour ? b : a));

  const statCards = h("div", { class: "stats" }, [
    ["Rx1day trung bình", fmt(S.rx1day.mean, 1), "mm", `lớn nhất ${fmt(max1.rx1day, 1)} mm (${fmtDate(max1.rx1day_date)})`, "orange"],
    ["Rx5day trung bình", fmt(S.rx5day.mean, 1), "mm", `lớn nhất ${fmt(max5.rx5day, 1)} mm (${fmtDM(max5.rx5day_start)}–${fmtDate(max5.rx5day_end)})`, "orange"],
    ["Rx1hour trung bình", fmt(S.rx1hour.mean, 1), "mm", `lớn nhất ${fmt(maxh.rx1hour, 1)} mm (${fmtDate(maxh.rx1hour_date)})`, ""],
    ["Tỉ số Rx5day/Rx1day", fmt(S.ratio.mean, 2), "", `dao động ${fmt(S.ratio.min, 2)}–${fmt(S.ratio.max, 2)}`, ""],
    ["Năm Rx1day trùng trượt lở", `${rows.filter((r) => r.slide_rx1).length}/10`, "năm", `giai đoạn Rx5day: ${rows.filter((r) => r.slide_rx5).length}/10 năm`, "slide"],
  ].map(([l, v, u, n, tone]) => h("div", { class: `stat ${tone}` }, h("div", { class: "label" }, l),
    h("div", { class: "value" }, v, u ? h("span", { class: "unit" }, u) : null), h("div", { class: "note" }, n))));

  const barCard = card("Rx1day, Rx5day và Rx1hour theo năm", { sub: "Bấm vào cột để xem đợt mưa của năm đó; Rx1hour theo trục phải" });
  const barEl = chartBox("tall");
  barCard.body.append(barEl);

  const tblCard = card("Bảng chỉ số cực trị theo năm", { sub: "Bấm vào dòng để xem đợt mưa; cờ đỏ: có trượt lở" });
  const evCard = card("", {});
  const evHead = h("div", {});
  const evEl = chartBox("tall");
  evCard.body.append(evHead, evEl, caption("Cột: mưa giờ; đường cam: lượng mưa tích lũy trong 5 ngày Rx5day; vùng xanh nhạt: giai đoạn Rx5day; vùng đỏ nhạt: giờ có trượt lở."));

  const stTable = card("Thống kê chuỗi cực trị (10 năm)", {});
  stTable.body.append(dataTable([
    { key: "label", label: "Chuỗi", align: "left", sortable: false },
    { key: "mean", label: "Trung bình", fmt: (v, r) => fmt(v, r.nd) }, { key: "std", label: "Độ lệch chuẩn", fmt: (v, r) => fmt(v, r.nd) },
    { key: "cv", label: "CV (%)", fmt: (v) => fmt(v, 1) }, { key: "min", label: "Nhỏ nhất", fmt: (v, r) => fmt(v, r.nd) },
    { key: "median", label: "Trung vị", fmt: (v, r) => fmt(v, r.nd) }, { key: "max", label: "Lớn nhất", fmt: (v, r) => fmt(v, r.nd) },
  ], [["Rx1day (mm)", S.rx1day, 1], ["Rx5day (mm)", S.rx5day, 1], ["Rx1hour (mm)", S.rx1hour, 1], ["Rx5day/Rx1day", S.ratio, 2]]
    .map(([label, s, nd]) => ({ label, nd, ...s })), { csvName: "thong_ke_cuc_tri.csv" }));

  host.replaceChildren(
    pageHead("Câu 2", "Mưa ngày lớn nhất năm và mưa 5 ngày liên tiếp lớn nhất năm",
      `${term("Rx1day", "Lượng mưa ngày lớn nhất trong năm")} là lượng mưa ngày lớn nhất trong năm; ${term("Rx5day", "Tổng lượng mưa lớn nhất của 5 ngày liên tiếp bất kỳ trong năm (tổng trượt 5 ngày)")} là tổng lượng mưa lớn nhất của 5 ngày liên tiếp bất kỳ. Trang này bổ sung ${term("Rx1hour", "Lượng mưa giờ lớn nhất trong năm")} để phục vụ phân tích mưa giờ. Theo định nghĩa của ETCCDI.`),
    statCards,
    h("div", { class: "grid grid-2" }, barCard.root, stTable.root),
    evCard.root, tblCard.root);

  const bar = chart(barEl, {
    tooltip: { trigger: "axis" },
    legend: { top: 0, left: 0 },
    xAxis: { type: "category", data: rows.map((r) => String(r.year)) },
    yAxis: [{ type: "value", name: "mm" }, { type: "value", name: "mm/giờ", splitLine: { show: false } }],
    series: [
      { name: "Rx1day", type: "bar", data: rows.map((r) => r.rx1day), itemStyle: { color: C.sea } },
      { name: "Rx5day", type: "bar", data: rows.map((r) => r.rx5day), itemStyle: { color: C.orange } },
      { name: "Rx1hour", type: "line", yAxisIndex: 1, data: rows.map((r) => r.rx1hour), itemStyle: { color: C.gold }, lineStyle: { type: "dashed" } },
    ],
  }, { label: "Biểu đồ Rx1day, Rx5day, Rx1hour theo năm" });
  bar.on("click", (p) => showYear(rows[p.dataIndex].year));

  tblCard.body.append(dataTable([
    { key: "year", label: "Năm", align: "left" },
    { key: "valid_day_pct", label: "Ngày hợp lệ (%)", fmt: (v) => fmt(v, 1) },
    { key: "rx1day", label: "Rx1day (mm)", fmt: (v) => fmt(v, 1) },
    { key: "rx1day_date", label: "Ngày xảy ra", fmt: (v, r) => `${fmtDate(v)}${r.slide_rx1 ? ' <span class="flag slide">trượt lở</span>' : ""}` },
    { key: "rx5day", label: "Rx5day (mm)", fmt: (v) => fmt(v, 1) },
    { key: "rx5day_start", label: "Giai đoạn 5 ngày", fmt: (v, r) => `${fmtDM(v)}–${fmtDM(r.rx5day_end)}${r.slide_rx5 ? ' <span class="flag slide">trượt lở</span>' : ""}` },
    { key: "rx1hour", label: "Rx1hour (mm)", fmt: (v) => fmt(v, 1) },
    { key: "rx1hour_date", label: "Thời điểm Rx1hour", fmt: (v, r) => `${fmtDate(v)} · ${r.rx1hour_hour} giờ` },
  ], rows, { csvName: "chi_so_cuc_tri.csv", onRowClick: (r) => showYear(r.year), rowClass: (r) => (r.year === year ? "selected" : "") }));

  let evChart = null;
  function showYear(y) {
    year = y;
    setParams({ nam: y });
    tblCard.root.querySelectorAll("tbody tr").forEach((tr) => tr.classList.toggle("selected", tr.firstChild.textContent === String(y)));
    const r = rows.find((x) => x.year === y);
    const ev = events.events.find((e) => e.year === y);
    const t0 = utcMs(ev.start);
    const t = (i) => t0 + (i + 1) * 3600000;
    const w0 = (utcMs(ev.window[0]) - t0) / 3600000;
    let acc = 0;
    const cum = ev.rain.map((v, i) => {
      if (i < w0 || i >= w0 + 120) return [t(i), null];
      acc += v || 0;
      return [t(i), +acc.toFixed(1)];
    });
    const maxH = Math.max(...ev.rain.map((v) => v ?? 0));
    evHead.replaceChildren(
      h("h3", {}, `Đợt mưa Rx5day năm ${y}: ${fmtDate(ev.window[0])}–${fmtDate(ev.window[1])}`),
      h("p", { class: "sub" }, `Tổng 5 ngày ${fmt(ev.total, 1)} mm; Rx1day ${fmt(r.rx1day, 1)} mm ngày ${fmtDate(r.rx1day_date)}${r.rx1_in_rx5 ? " (nằm trong đợt)" : " (ngoài đợt này)"}; giờ mưa lớn nhất trong đợt ${fmt(maxH, 1)} mm. `,
        h("a", { href: `#/tra-cuu?ngay=${r.rx1day_date}` }, "Tra cứu ngày Rx1day")),
      r.slide_rx5 ? notice(`Có ${ev.slide.length} giờ ghi nhận trượt lở trong cửa sổ hiển thị.`, "warn") : null);
    const opt = {
      tooltip: { trigger: "axis" },
      legend: { top: 0, right: 40 },
      grid: { top: 50 },
      xAxis: { type: "time", axisLabel: { formatter: "{dd}/{MM}\n{HH}:00" } },
      yAxis: [{ type: "value", name: "mm/giờ", max: (v) => Math.ceil(Math.max(v.max * 1.1, thr.blocks.hour_all.R99p * 1.05) / 10) * 10 }, { type: "value", name: "Tích lũy (mm)", splitLine: { show: false } }],
      series: [
        {
          name: "Mưa giờ", type: "bar", data: ev.rain.map((v, i) => [t(i), v]), itemStyle: { color: C.rain },
          markArea: {
            silent: true,
            data: [[{ xAxis: utcMs(ev.window[0]), itemStyle: { color: "rgba(156,195,217,.18)" } }, { xAxis: utcMs(ev.window[1]) + 86400000 }],
              ...ev.slide.map((i) => [{ xAxis: t(i - 1), itemStyle: { color: "rgba(122,31,31,.18)" } }, { xAxis: t(i) }])],
          },
        },
        { name: "Lũy kế 5 ngày", type: "line", yAxisIndex: 1, showSymbol: false, data: cum, lineStyle: { color: C.orange, width: 2.5 }, itemStyle: { color: C.orange } },
      ],
    };
    if (!evChart) evChart = chart(evEl, opt, { label: "Biểu đồ đợt mưa Rx5day" });
    else evChart.setOption(opt);
  }

  showYear(year);
}

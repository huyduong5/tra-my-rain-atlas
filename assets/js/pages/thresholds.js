import { load } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, term, tabs } from "../components.js";
import { chart, C, axisName, markLines } from "../charts.js";
import { fmt, fmtInt, ROMAN } from "../format.js";
import { interp, periodOf } from "../stats.js";

export async function render(host) {
  const [thr, ret] = await load("thresholds", "returns");
  const B = thr.blocks;

  const cards = h("div", { class: "stats" }, [
    ["Giờ mưa rất lớn (R95p)", B.hour_all.R95p, "mm/giờ", `${fmt(B.hour_all.per_year95, 1)} giờ/năm vượt ngưỡng`, ""],
    ["Giờ mưa cực kỳ lớn (R99p)", B.hour_all.R99p, "mm/giờ", `${fmt(B.hour_all.per_year99, 1)} giờ/năm vượt ngưỡng`, "orange"],
    ["Ngày mưa rất lớn (R95p)", B.day_all.R95p, "mm/ngày", `${fmt(B.day_all.per_year95, 1)} ngày/năm vượt ngưỡng`, ""],
    ["Ngày mưa cực kỳ lớn (R99p)", B.day_all.R99p, "mm/ngày", `${fmt(B.day_all.per_year99, 1)} ngày/năm vượt ngưỡng`, "orange"],
  ].map(([l, v, u, n, tone]) => h("div", { class: `stat ${tone}` }, h("div", { class: "label" }, l),
    h("div", { class: "value" }, fmt(v, 1), h("span", { class: "unit" }, u)), h("div", { class: "note" }, n))));

  // Bảng ngưỡng như báo cáo
  const tCard = card("Ngưỡng R95p, R99p và các đặc trưng liên quan", { sub: "Mẫu: giờ/ngày mưa ≥ 1 mm, 2008–2017; đóng góp = tổng lượng mưa vượt ngưỡng / tổng lượng mưa của các giờ (ngày) mưa" });
  const keys = [["hour_all", "Giờ — cả năm"], ["hour_rainy", "Giờ — mùa mưa"], ["day_all", "Ngày — cả năm"], ["day_rainy", "Ngày — mùa mưa"]];
  const rowsDef = [["n_wet", "Số giờ/ngày mưa ≥ 1 mm", 0], ["R95p", "R95p (mm)", 1], ["R99p", "R99p (mm)", 1], ["n95", "Số lần vượt R95p", 0],
    ["n99", "Số lần vượt R99p", 0], ["per_year95", "Vượt R95p trung bình/năm", 1], ["per_year99", "Vượt R99p trung bình/năm", 1],
    ["share95", "Đóng góp của các lần > R95p (%)", 1], ["share99", "Đóng góp của các lần > R99p (%)", 1]];
  tCard.body.append(dataTable([{ key: "label", label: "Chỉ tiêu", align: "left", sortable: false },
    ...keys.map(([k, l]) => ({ key: k, label: l, sortable: false, fmt: (v, r) => fmt(v, r.nd) }))],
  rowsDef.map(([k, label, nd]) => ({ label, nd, ...Object.fromEntries(keys.map(([kk]) => [kk, B[kk][k]])) })), { csvName: "nguong_r95p_r99p.csv" }));

  // Công cụ tra cứu
  const calc = card("Công cụ: một lượng mưa thuộc mức nào?", { sub: "Nhập lượng mưa giờ hoặc ngày để biết phân vị, mức phân cấp và chu kỳ lặp lại tương đương" });
  const kind = h("select", {}, h("option", { value: "day" }, "Mưa ngày (mm/ngày)"), h("option", { value: "hour" }, "Mưa giờ (mm/giờ)"));
  const amount = h("input", { type: "number", min: "0", step: "0.1", value: "150", "aria-label": "Lượng mưa" });
  const out = h("div", { class: "calc-result", "aria-live": "polite" });
  calc.body.append(h("div", { class: "toolbar", style: "margin:0 0 .5rem" },
    h("label", { class: "field" }, "Loại", kind), h("label", { class: "field" }, "Lượng mưa (mm)", amount)), out);
  const evaluate = () => {
    const k = kind.value;
    const v = parseFloat(amount.value);
    if (!(v >= 0)) { out.textContent = "Nhập một số không âm."; return; }
    const arr = thr.percentiles[k];
    const blk = k === "day" ? B.day_all : B.hour_all;
    const unit = k === "day" ? "mm/ngày" : "mm/giờ";
    let p;
    if (v < 1) p = null;
    else if (v < arr[0]) p = "dưới 1";
    else if (v > arr[arr.length - 1]) p = "trên 99,9";
    else p = fmt(interp(v, arr, thr.percentiles.levels), 1);
    const level = v > blk.R99p ? "cực kỳ lớn (vượt R99p)" : v > blk.R95p ? "rất lớn (vượt R95p)" : v >= 1 ? "dưới ngưỡng rất lớn" : "không tính là mưa (< 1 mm)";
    const s = ret.series[k];
    const T = periodOf(v, ret.T_grid, s.models[s.selected].grid);
    out.replaceChildren(
      h("p", {}, `${fmt(v, 1)} ${unit} là mức `, h("strong", {}, level), "."),
      p ? h("p", {}, `Thuộc phân vị khoảng ${p} trong các ${k === "day" ? "ngày" : "giờ"} mưa ≥ 1 mm của Trà My (2008–2017).`) : null,
      h("p", {}, T ? `Nếu là giá trị lớn nhất năm, tương đương chu kỳ lặp lại khoảng ${fmt(T, T < 10 ? 1 : 0)} năm (phân bố ${s.selected}). ` :
        v > s.models[s.selected].grid.at(-1) ? "Vượt mức chu kỳ 1000 năm của mô hình. " : "Nhỏ hơn mức cực đại năm thông thường. ",
      h("a", { href: `#/chu-ky?chuoi=${k === "day" ? "ngay" : "gio"}` }, "Xem trang Chu kỳ lặp")));
  };
  kind.addEventListener("change", () => { amount.value = kind.value === "day" ? "150" : "40"; evaluate(); });
  amount.addEventListener("input", evaluate);

  const hCard = card("Phân bố và ngưỡng", { sub: "Trục tung thang log; vạch: R95p và R99p (cả năm)" });
  const hTabsHost = h("div", {});
  const hEl = chartBox();
  hCard.body.append(hTabsHost, hEl);

  const yCard = card("Số lần vượt ngưỡng theo năm", { sub: "Ngưỡng tính cho cả năm" });
  const yTabs = h("div", {});
  const yEl = chartBox();
  yCard.body.append(yTabs, yEl);
  const mCard = card("Số lần vượt R95p theo tháng", { sub: "Tổng 10 năm; mưa rất lớn tập trung tháng IX–XII" });
  const mEl = chartBox();
  mCard.body.append(mEl, caption("Mưa giờ rất lớn vẫn xuất hiện trong mùa khô (tháng V–VIII) do mưa dông."));

  host.replaceChildren(
    pageHead("Câu 3", "Ngưỡng mưa giờ, mưa ngày rất lớn (R95p) và cực kỳ lớn (R99p)",
      `Theo ETCCDI, ${term("R95p", "Phân vị 95% của lượng mưa các ngày mưa ≥ 1 mm trong thời kỳ cơ sở")} và ${term("R99p", "Phân vị 99% của lượng mưa các ngày mưa ≥ 1 mm trong thời kỳ cơ sở")} là phân vị 95% và 99% của lượng mưa trong các ngày mưa (≥ 1 mm). Cách tính tương tự được áp dụng cho mưa giờ. Thời kỳ cơ sở là toàn bộ số liệu hợp lệ 2008–2017; phân vị tính bằng nội suy tuyến tính.`),
    cards,
    h("div", { class: "grid grid-2" }, calc.root, hCard.root),
    tCard.root,
    h("div", { class: "grid grid-2" }, yCard.root, mCard.root));

  let hChart = null;
  const drawHist = (k) => {
    const hist = thr.hist[k];
    const blk = k === "day" ? B.day_all : B.hour_all;
    const mids = hist.counts.map((_, i) => (hist.edges[i] + hist.edges[i + 1]) / 2);
    const opt = {
      tooltip: { trigger: "axis", formatter: (p) => `${fmt(hist.edges[p[0].dataIndex], 0)}–${fmt(hist.edges[p[0].dataIndex + 1], 0)} mm: ${fmtInt(p[0].value[1])} lần` },
      xAxis: { type: "value", min: 0, ...axisName(k === "day" ? "mm/ngày" : "mm/giờ") },
      yAxis: { type: "log", min: 1, ...axisName("Số lần (log)", { nameGap: 44 }) },
      series: [{
        type: "bar", barWidth: "95%", data: mids.map((m, i) => [m, hist.counts[i] || null]),
        itemStyle: { color: C.soft },
        markLine: markLines([[blk.R95p, C.gold, `R95p ${fmt(blk.R95p, 1)}`, "xAxis"], [blk.R99p, C.orange, `R99p ${fmt(blk.R99p, 1)}`, "xAxis"]]),
      }],
    };
    if (!hChart) hChart = chart(hEl, opt, { label: "Histogram và ngưỡng R95p, R99p" });
    else hChart.setOption(opt);
  };
  hTabsHost.append(tabs([["day", "Mưa ngày"], ["hour", "Mưa giờ"]], "day", drawHist));
  drawHist("day");

  let yChart = null;
  const drawYear = (k) => {
    const opt = {
      tooltip: { trigger: "axis" },
      legend: { top: 0, left: 0 },
      xAxis: { type: "category", data: thr.by_year.map((r) => String(r.year)) },
      yAxis: { type: "value", name: k === "day" ? "Số ngày" : "Số giờ" },
      series: [
        { name: "> R95p", type: "bar", data: thr.by_year.map((r) => r[`${k}95`]), itemStyle: { color: C.gold }, label: { show: true, position: "top", fontSize: 10 } },
        { name: "> R99p", type: "bar", data: thr.by_year.map((r) => r[`${k}99`]), itemStyle: { color: C.orange }, label: { show: true, position: "top", fontSize: 10 } },
      ],
    };
    if (!yChart) yChart = chart(yEl, opt, { label: "Số lần vượt ngưỡng theo năm" });
    else yChart.setOption(opt);
  };
  yTabs.append(tabs([["day", "Ngày"], ["hour", "Giờ"]], "day", drawYear));
  drawYear("day");

  chart(mEl, {
    tooltip: { trigger: "axis" },
    legend: { top: 0, left: 0 },
    xAxis: { type: "category", data: ROMAN.slice(1) },
    yAxis: [{ type: "value", name: "Số giờ" }, { type: "value", name: "Số ngày", splitLine: { show: false } }],
    series: [
      { name: "Giờ > R95p", type: "bar", data: thr.by_month.map((r) => r.hour95), itemStyle: { color: C.soft } },
      { name: "Ngày > R95p", type: "line", yAxisIndex: 1, data: thr.by_month.map((r) => r.day95), itemStyle: { color: C.orange } },
    ],
  }, { label: "Số lần vượt R95p theo tháng" });

  evaluate();
}

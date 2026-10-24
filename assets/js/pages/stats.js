import { load } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, tabs, notice, term, shareButton } from "../components.js";
import { chart, C, axisName, disposeAll } from "../charts.js";
import { fmt, fmtInt, fmtDate, ROMAN, addDays } from "../format.js";
import { setParams, go } from "../router.js";
import { rainStats, describe, boxStats } from "../stats.js";

const RAINY = [9, 10, 11, 12];
const SEASONS = [["all", "Cả năm"], ["rainy", "Mùa mưa (IX–XII)"], ["dry", "Mùa khô (I–VIII)"]];

/** Bảng thông số mưa như báo cáo: cột = các nhóm */
function statTable(groups, unit, big) {
  const rows = [
    ["n", `Số ${unit} có số liệu`, 0], ["mean", "Trung bình (mm)", 2], ["std", "Độ lệch chuẩn (mm)", 2], ["cv", "CV (%)", 1],
    ["median", "Trung vị (mm)", 1], ["p75", "Phân vị 75% (mm)", 1], ["p90", "Phân vị 90% (mm)", 1], ["p95", "Phân vị 95% (mm)", 1],
    ["p99", "Phân vị 99% (mm)", 1], ["max", "Lớn nhất (mm)", 1], ["skew", "Độ lệch (skewness)", 2],
    ["n_wet", `Số ${unit} mưa ≥ 1 mm`, 0], ["freq_wet", `Tần suất ${unit} mưa (%)`, 1], ["mean_wet", `Mưa TB ${unit} mưa (mm)`, 2],
    ["median_wet", `Trung vị ${unit} mưa (mm)`, 1], ["n_big1", `Số ${unit} mưa > ${big[0]} mm`, 0], ["n_big2", `Số ${unit} mưa > ${big[1]} mm`, 0],
  ].map(([k, label, nd]) => {
    const r = { label };
    groups.forEach(([gk], j) => { r[`c${j}`] = groups[j][2][k]; r[`nd`] = nd; });
    return r;
  });
  return dataTable([{ key: "label", label: "Thông số", align: "left", sortable: false },
    ...groups.map(([, title], j) => ({ key: `c${j}`, label: title, sortable: false, fmt: (v, r) => fmt(v, r.nd) }))],
  rows, { csvName: `thong_ke_mua_${unit}.csv` });
}

export async function render(host, params) {
  const [summary, daily, monthly, annual, thr] = await load("summary", "daily", "monthly", "annual", "thresholds");
  const tab = ["gio", "ngay", "thang", "nam"].includes(params.muc) ? params.muc : "ngay";
  let y0 = +params.tu || 2008;
  let y1 = +params.den || 2017;

  const content = h("div", {});
  const yearSel = (val, onChange) => {
    const s = h("select", {}, Array.from({ length: 10 }, (_, k) => h("option", { value: 2008 + k, selected: 2008 + k === val }, 2008 + k)));
    s.addEventListener("change", () => onChange(+s.value));
    return s;
  };
  let current = tab;
  const draw = () => {
    disposeAll();
    setParams({ muc: current, tu: y0 !== 2008 ? y0 : null, den: y1 !== 2017 ? y1 : null });
    if (current === "gio") drawHourly();
    if (current === "ngay") drawDaily();
    if (current === "thang") drawMonthly();
    if (current === "nam") drawAnnual();
  };
  const filter = () => h("div", { class: "toolbar" },
    h("label", { class: "field" }, "Từ năm", yearSel(y0, (v) => { y0 = Math.min(v, y1); draw(); })),
    h("label", { class: "field" }, "Đến năm", yearSel(y1, (v) => { y1 = Math.max(v, y0); draw(); })),
    h("button", { class: "btn", type: "button", onclick: () => { y0 = 2008; y1 = 2017; draw(); } }, "Toàn bộ 2008–2017"),
    shareButton());

  host.replaceChildren(
    pageHead("Câu 1", "Thống kê mưa giờ, ngày, tháng, năm và theo mùa",
      `Các đặc trưng thống kê thông thường tính trên số liệu hợp lệ: ${term("ngày hợp lệ", "Ngày có ít nhất 20/24 giờ có số liệu")}, ${term("tháng hợp lệ", "Tháng có ít nhất 90% số ngày hợp lệ")}. Mùa mưa tại Trà My là các tháng IX–XII. Có thể lọc theo khoảng năm; kết quả toàn giai đoạn trùng với báo cáo (có thể lệch ở chữ số làm tròn cuối cùng).`),
    tabs([["gio", "Mưa giờ"], ["ngay", "Mưa ngày"], ["thang", "Mưa tháng"], ["nam", "Mưa năm và mùa"]], tab, (id) => { current = id; draw(); }),
    content);

  // ---------- Mưa giờ ----------
  function drawHourly() {
    const t = card("Thống kê mô tả mưa giờ", { sub: "Toàn giai đoạn 2008–2017, trên 84 429 giờ có số liệu" });
    const groups = SEASONS.map(([k, label]) => [k, label, summary.hourly[k]]);
    t.body.append(statTable(groups, "giờ", [20, 50]));
    const d = card("Chu trình ngày của mưa giờ", { sub: "Lượng mưa trung bình theo giờ trong ngày, tách mùa" });
    const dEl = chartBox();
    d.body.append(dEl, caption("Mùa khô mưa dông tập trung buổi chiều (cực đại 16–17 giờ); mùa mưa mưa đều suốt ngày."));
    const hi = card("Phân bố mưa giờ (giờ mưa ≥ 1 mm)", { sub: "Trục tung thang log" });
    const hiEl = chartBox();
    hi.body.append(hiEl);
    const top = card("10 giờ mưa lớn nhất", { sub: "Bấm vào dòng để mở trang Tra cứu ngày đó" });
    top.body.append(dataTable([
      { key: "d", label: "Ngày", align: "left", fmt: (v) => fmtDate(v) }, { key: "h", label: "Giờ" }, { key: "v", label: "Mưa (mm)", fmt: (v) => fmt(v, 1) },
    ], summary.top_hours.map(([d, hh, v]) => ({ d, h: hh, v })), { onRowClick: (r) => go("tra-cuu", { ngay: r.d }) }));
    content.replaceChildren(notice("Thống kê mưa giờ luôn tính cho toàn giai đoạn (không áp dụng bộ lọc năm)."),
      t.root, h("div", { class: "grid grid-2" }, d.root, hi.root), top.root);
    const hours = Array.from({ length: 24 }, (_, k) => k + 1);
    chart(dEl, {
      legend: { top: 0, left: 0 },
      xAxis: { type: "category", data: hours, ...axisName("Giờ trong ngày") },
      yAxis: { type: "value", ...axisName("mm/giờ", { nameGap: 44 }) },
      series: [
        { name: "Mùa mưa (IX–XII)", type: "line", data: summary.diurnal.rainy.mean, itemStyle: { color: C.orange } },
        { name: "Mùa khô (I–VIII)", type: "line", data: summary.diurnal.dry.mean, itemStyle: { color: C.sea } },
      ],
    }, { label: "Chu trình ngày của mưa giờ" });
    histChart(hiEl, thr.hist.hour, "mm/giờ");
  }

  function histChart(el, hist, unit) {
    const mids = hist.counts.map((_, i) => (hist.edges[i] + hist.edges[i + 1]) / 2);
    chart(el, {
      tooltip: { trigger: "axis", formatter: (p) => `${fmt(hist.edges[p[0].dataIndex], 0)}–${fmt(hist.edges[p[0].dataIndex + 1], 0)} ${unit}: ${fmtInt(p[0].value[1])} lần` },
      xAxis: { type: "value", ...axisName(unit), min: 0 },
      yAxis: { type: "log", ...axisName("Số lần (log)", { nameGap: 44 }), min: 1 },
      series: [{ type: "bar", barWidth: "95%", data: mids.map((m, i) => [m, hist.counts[i] || null]), itemStyle: { color: C.rain } }],
    }, { label: `Histogram ${unit}` });
  }

  // ---------- Mưa ngày ----------
  function drawDaily() {
    const vals = { all: [], rainy: [], dry: [] };
    daily.rain.forEach((v, i) => {
      if (v === null) return;
      const d = addDays(daily.start, i);
      const y = +d.slice(0, 4);
      if (y < y0 || y > y1) return;
      const m = +d.slice(5, 7);
      vals.all.push(v);
      (RAINY.includes(m) ? vals.rainy : vals.dry).push(v);
    });
    const groups = SEASONS.map(([k, label]) => [k, label, rainStats(vals[k], [50, 100])]);
    const t = card(`Thống kê mô tả mưa ngày ${y0}–${y1}`, { sub: "Trên các ngày hợp lệ (≥ 20 giờ có số liệu)" });
    t.body.append(statTable(groups, "ngày", [50, 100]));
    const hi = card("Phân bố mưa ngày (ngày mưa ≥ 1 mm)", { sub: "Trục tung thang log; cả giai đoạn" });
    const hiEl = chartBox();
    hi.body.append(hiEl);
    const top = card("Ngày mưa lớn nhất trong khoảng chọn", { sub: "Bấm vào dòng để xem mưa từng giờ" });
    const list = [];
    daily.rain.forEach((v, i) => {
      if (v === null) return;
      const d = addDays(daily.start, i);
      if (+d.slice(0, 4) < y0 || +d.slice(0, 4) > y1) return;
      list.push({ d, v, slide: daily.slide.includes(i) });
    });
    list.sort((a, b) => b.v - a.v);
    top.body.append(dataTable([
      { key: "d", label: "Ngày", align: "left", fmt: (v) => fmtDate(v) },
      { key: "v", label: "Mưa (mm)", fmt: (v) => fmt(v, 1) },
      { key: "slide", label: "Trượt lở", fmt: (v) => (v ? '<span class="flag slide">có</span>' : "") },
    ], list.slice(0, 20), { onRowClick: (r) => go("tra-cuu", { ngay: r.d }), csvName: "ngay_mua_lon_nhat.csv" }));
    content.replaceChildren(filter(), t.root, h("div", { class: "grid grid-2" }, hi.root, top.root));
    histChart(hiEl, thr.hist.day, "mm/ngày");
  }

  // ---------- Mưa tháng ----------
  function drawMonthly() {
    const rows = monthly.rows.map(([year, month, total, vd, days, valid, wet, maxd]) => ({ year, month, total, vd, days, valid, wet, maxd }))
      .filter((r) => r.year >= y0 && r.year <= y1);
    const ok = rows.filter((r) => r.valid);
    const clim = Array.from({ length: 12 }, (_, k) => {
      const s = describe(ok.filter((r) => r.month === k + 1).map((r) => r.total));
      return { month: k + 1, ...s };
    });
    const t = card(`Thống kê tổng lượng mưa theo tháng ${y0}–${y1}`, { sub: "Chỉ tính tháng hợp lệ (≥ 90% ngày hợp lệ)" });
    t.body.append(dataTable([
      { key: "month", label: "Tháng", align: "left", fmt: (v) => ROMAN[v] },
      { key: "n", label: "Số tháng" }, { key: "mean", label: "Trung bình (mm)", fmt: (v) => fmt(v, 1) },
      { key: "std", label: "Độ lệch chuẩn", fmt: (v) => fmt(v, 1) }, { key: "cv", label: "CV (%)", fmt: (v) => fmt(v, 0) },
      { key: "min", label: "Nhỏ nhất", fmt: (v) => fmt(v, 1) }, { key: "median", label: "Trung vị", fmt: (v) => fmt(v, 1) },
      { key: "max", label: "Lớn nhất", fmt: (v) => fmt(v, 1) },
    ], clim, { csvName: "khi_hau_thang.csv" }));
    const b = card("Biểu đồ hộp tổng lượng mưa tháng", { sub: "Hộp: phân vị 25–75%; vạch giữa: trung vị; râu: nhỏ nhất–lớn nhất; cam: mùa mưa" });
    const bEl = chartBox();
    b.body.append(bEl);
    const hm = card("Tổng lượng mưa từng tháng", { sub: "Ô gạch: tháng không hợp lệ (11/2009, 01/2017)" });
    const hmEl = chartBox();
    hm.body.append(hmEl);
    const all = card("Bảng chi tiết từng tháng", { sub: "Lọc nhanh theo năm hoặc tháng; tải CSV" });
    all.body.append(dataTable([
      { key: "year", label: "Năm", align: "left" }, { key: "month", label: "Tháng" },
      { key: "total", label: "Tổng (mm)", fmt: (v) => fmt(v, 1) }, { key: "vd", label: "Ngày hợp lệ", fmt: (v, r) => `${v}/${r.days}` },
      { key: "wet", label: "Ngày mưa" }, { key: "maxd", label: "Mưa ngày lớn nhất", fmt: (v) => fmt(v, 1) },
      { key: "valid", label: "Hợp lệ", fmt: (v) => (v ? '<span class="flag ok">có</span>' : '<span class="flag warn">không</span>') },
    ], rows, { search: true, csvName: "mua_thang.csv", maxHeight: "420px" }));
    const s = describe(ok.map((r) => r.total));
    content.replaceChildren(filter(),
      h("div", { class: "stats" }, [
        ["Số tháng hợp lệ", fmtInt(s.n), ""], ["Trung bình tháng", fmt(s.mean, 1), "mm"], ["Trung vị", fmt(s.median, 1), "mm"],
        ["CV", fmt(s.cv, 1), "%"], ["Tháng lớn nhất", fmt(s.max, 1), "mm"],
      ].map(([l, v, u]) => h("div", { class: "stat" }, h("div", { class: "label" }, l), h("div", { class: "value" }, v, u ? h("span", { class: "unit" }, u) : null)))),
      t.root, h("div", { class: "grid grid-2" }, b.root, hm.root), all.root);
    chart(bEl, {
      tooltip: { trigger: "item" },
      xAxis: { type: "category", data: ROMAN.slice(1), ...axisName("Tháng") },
      yAxis: { type: "value", ...axisName("mm", { nameGap: 48 }) },
      series: [{
        type: "boxplot",
        data: clim.map((c) => ({ value: boxStats(ok.filter((r) => r.month === c.month).map((r) => r.total)), itemStyle: { color: RAINY.includes(c.month) ? "#f3d2bf" : "#d5e6f0", borderColor: RAINY.includes(c.month) ? C.orange : C.sea } })),
        tooltip: { formatter: (p) => { const v = p.value; return `Tháng ${ROMAN[p.dataIndex + 1]}<br>Lớn nhất: ${fmt(v[5], 1)}<br>Q3: ${fmt(v[4], 1)}<br>Trung vị: ${fmt(v[3], 1)}<br>Q1: ${fmt(v[2], 1)}<br>Nhỏ nhất: ${fmt(v[1], 1)}`; } },
      }],
    }, { label: "Biểu đồ hộp tổng lượng mưa tháng" });
    const years = [];
    for (let y = y0; y <= y1; y++) years.push(y);
    chart(hmEl, {
      tooltip: { trigger: "item", formatter: (p) => `${ROMAN[p.data[0] + 1]}/${years[p.data[1]]}: ${fmt(p.data[2], 1)} mm${p.data[3] ? "" : " (không hợp lệ)"}` },
      grid: { left: 50, right: 20, top: 10, bottom: 70 },
      xAxis: { type: "category", data: ROMAN.slice(1) },
      yAxis: { type: "category", data: years.map(String), inverse: true },
      visualMap: { min: 0, max: 1500, dimension: 2, calculable: true, orient: "horizontal", left: "center", bottom: 0, itemHeight: 140, inRange: { color: ["#f2f6f8", "#9cc3d9", "#3a7ca5", "#1b4b63", "#c45c26"] }, text: ["≥1500 mm", "0"] },
      series: [{
        type: "heatmap",
        data: rows.map((r) => [r.month - 1, years.indexOf(r.year), r.total, r.valid ? 1 : 0]),
        label: { show: true, fontSize: 9, formatter: (p) => (p.data[3] ? Math.round(p.data[2]) : `${Math.round(p.data[2])}*`) },
        itemStyle: { borderColor: "#fff", borderWidth: 1 },
      }],
    }, { label: "Lịch nhiệt tổng lượng mưa tháng" });
  }

  // ---------- Mưa năm và mùa ----------
  function drawAnnual() {
    const rows = annual.rows.filter((r) => r.year >= y0 && r.year <= y1);
    const st = (key, okKey) => describe(rows.filter((r) => r[okKey]).map((r) => r[key]));
    const shares = rows.filter((r) => r.ok_year).map((r) => (100 * r.rainy) / r.total);
    const sumRows = [
      ["Mưa năm (mm)", st("total", "ok_year")], ["Mùa mưa IX–XII (mm)", st("rainy", "ok_rainy")],
      ["Mùa khô I–VIII (mm)", st("dry", "ok_dry")], ["Tỉ lệ mùa mưa (%)", describe(shares)], ["Số ngày mưa", st("wet_days", "ok_year")],
    ].map(([label, s]) => ({ label, ...s }));
    const t = card(`Thống kê lượng mưa năm và theo mùa ${y0}–${y1}`, { sub: "Chỉ tính năm/mùa có đủ tháng hợp lệ" });
    t.body.append(dataTable([
      { key: "label", label: "Chuỗi", align: "left", sortable: false }, { key: "n", label: "n" },
      { key: "mean", label: "Trung bình", fmt: (v) => fmt(v, 1) }, { key: "std", label: "Độ lệch chuẩn", fmt: (v) => fmt(v, 1) },
      { key: "cv", label: "CV (%)", fmt: (v) => fmt(v, 1) }, { key: "min", label: "Nhỏ nhất", fmt: (v) => fmt(v, 1) },
      { key: "median", label: "Trung vị", fmt: (v) => fmt(v, 1) }, { key: "max", label: "Lớn nhất", fmt: (v) => fmt(v, 1) },
      { key: "skew", label: "Độ lệch", fmt: (v) => fmt(v, 2) },
    ], sumRows, { csvName: "thong_ke_nam_mua.csv" }));
    const c = card("Lượng mưa năm theo mùa", { sub: "Cột nhạt: năm có tháng thiếu số liệu (giá trị thấp hơn thực tế)" });
    const cEl = chartBox("tall");
    c.body.append(cEl);
    const tbl = card("Bảng theo năm", {});
    tbl.body.append(dataTable([
      { key: "year", label: "Năm", align: "left", fmt: (v, r) => `${v}${r.ok_year ? "" : " *"}` },
      { key: "total", label: "Mưa năm (mm)", fmt: (v) => fmt(v, 1) }, { key: "rainy", label: "Mùa mưa (mm)", fmt: (v) => fmt(v, 1) },
      { key: "dry", label: "Mùa khô (mm)", fmt: (v) => fmt(v, 1) },
      { key: "share", label: "Tỉ lệ mùa mưa (%)", fmt: (v) => fmt(v, 1) }, { key: "wet_days", label: "Số ngày mưa" },
      { key: "max_day", label: "Mưa ngày lớn nhất", fmt: (v) => fmt(v, 1) }, { key: "valid_day_pct", label: "Ngày hợp lệ (%)", fmt: (v) => fmt(v, 1) },
    ], rows.map((r) => ({ ...r, share: (100 * r.rainy) / r.total })), { csvName: "mua_nam.csv" }),
    h("p", { class: "caption" }, "* Năm có tháng không hợp lệ (11/2009 hoặc 01/2017): tổng năm thấp hơn thực tế, không đưa vào bảng thống kê."));
    content.replaceChildren(filter(), t.root, c.root, tbl.root);
    chart(cEl, {
      tooltip: { trigger: "axis" },
      legend: { top: 0, left: 0 },
      xAxis: { type: "category", data: rows.map((r) => `${r.year}${r.ok_year ? "" : "*"}`) },
      yAxis: [{ type: "value", name: "mm" }, { type: "value", name: "Số ngày mưa", splitLine: { show: false } }],
      series: [
        { name: "Mùa khô (I–VIII)", type: "bar", stack: "s", data: rows.map((r) => ({ value: r.dry, itemStyle: { color: C.soft, opacity: r.ok_dry ? 1 : 0.45 } })) },
        { name: "Mùa mưa (IX–XII)", type: "bar", stack: "s", data: rows.map((r) => ({ value: r.rainy, itemStyle: { color: C.orange, opacity: r.ok_rainy ? 1 : 0.45 } })),
          label: { show: true, position: "top", formatter: (p) => fmt(rows[p.dataIndex].total, 0), fontSize: 10 } },
        { name: "Số ngày mưa ≥ 1 mm", type: "line", yAxisIndex: 1, data: rows.map((r) => r.wet_days), itemStyle: { color: C.ink } },
      ],
    }, { label: "Lượng mưa năm theo mùa" });
  }

  draw();
}

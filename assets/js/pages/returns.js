import { load } from "../data.js";
import { h, card, chartBox, caption, pageHead, dataTable, term, notice, shareButton } from "../components.js";
import { chart, C, axisName } from "../charts.js";
import { fmt } from "../format.js";
import { setParams } from "../router.js";
import { levelAt, periodOf } from "../stats.js";

const MODELS = [
  ["gumbel", "Gumbel", "Gumbel (MLE)"], ["gev", "GEV", "GEV (MLE)"], ["ln2", "Chuẩn loga", "Chuẩn loga (MLE)"],
  ["gamma", "Gamma", "Gamma (MLE)"], ["weibull", "Weibull", "Weibull (MLE)"],
  ["lmom", "L-moment", "Gumbel (L-moment)"], ["pot", "POT", "POT–GPD (vượt ngưỡng)"], ["drop", "Bỏ max", "Gumbel bỏ giá trị lớn nhất"],
];
const COLORS = { gumbel: C.sea, gev: C.grey, ln2: C.orange, gamma: C.gold, weibull: C.green, lmom: C.rain, pot: C.slide, drop: "#9b8bb4" };

function gridOf(s, id) {
  const m = MODELS.find((x) => x[0] === id)[1];
  if (id === "lmom") return s.lmoment.grid;
  if (id === "pot") return s.pot.grid;
  if (id === "drop") return s.drop_max.grid;
  return s.models[m].grid;
}

export async function render(host, params) {
  const [ret] = await load("returns");
  const G = ret.T_grid;
  let key = params.chuoi === "gio" ? "hour" : "day";
  let model = MODELS.some((m) => m[0] === params.mohinh) ? params.mohinh : "gumbel";

  const serSel = h("select", {}, h("option", { value: "day", selected: key === "day" }, "Mưa ngày — Rx1day"), h("option", { value: "hour", selected: key === "hour" }, "Mưa giờ — Rx1hour"));
  const modSel = h("select", {}, MODELS.map(([id, , label]) => h("option", { value: id, selected: id === model }, label)));
  const tInput = h("input", { type: "number", min: "1.1", max: "1000", step: "1", value: params.T || "100", "aria-label": "Chu kỳ lặp lại (năm)" });
  const vInput = h("input", { type: "number", min: "0", step: "1", value: "", placeholder: "vd. 500", "aria-label": "Lượng mưa (mm)" });
  const calcOut = h("div", { class: "calc-result", "aria-live": "polite" });

  const tableCard = card("", {});
  const chartCard = card("Đường tần suất", { sub: "Trục hoành: chu kỳ lặp lại T (năm, thang log). Điểm đen: giá trị quan trắc theo công thức Gringorten. Dải xanh: khoảng tin cậy 95% (bootstrap tham số 2000 lần) của Gumbel." });
  const chartEl = chartBox("tall");
  chartCard.body.append(chartEl);
  const cmpCard = card("So sánh các mô hình", { sub: "Mức mưa (mm) theo từng phương án — đánh giá độ nhạy của kết quả" });
  const fitCard = card("Mức độ phù hợp của các phân bố (MLE)", { sub: "AIC, BIC càng nhỏ càng tốt; KS, CvM, AD là khoảng cách giữa phân phối thực nghiệm và lý thuyết (càng nhỏ càng tốt)" });

  host.replaceChildren(
    pageHead("Câu 4", "Mưa giờ, mưa ngày cực đại theo chu kỳ lặp lại",
      `Phân tích tần suất trên ${term("chuỗi cực đại năm (AMS)", "Mỗi năm lấy một giá trị lớn nhất: Rx1day cho mưa ngày, Rx1hour cho mưa giờ")}: khớp 5 phân bố bằng hợp lý cực đại, chọn Gumbel theo AIC (chênh lệch AIC dưới 2 thì ưu tiên Gumbel), ${term("khoảng tin cậy 95%", "Ước lượng bằng bootstrap tham số: sinh 2000 mẫu cỡ 10 từ phân bố đã khớp, khớp lại và lấy phân vị 2,5% và 97,5%")} bằng bootstrap. Trình bày theo kiểu NOAA Atlas 14 (PFDS).`),
    notice("Chuỗi chỉ có 10 năm nên mức 50–100 năm là ngoại suy xa (gấp 5–10 lần độ dài chuỗi), khoảng tin cậy rất rộng. Chỉ dùng tham khảo; với thiết kế công trình cần chuỗi dài hơn hoặc phân tích tần suất vùng.", "warn"),
    h("div", { class: "toolbar" },
      h("label", { class: "field" }, "Chuỗi số liệu", serSel),
      h("label", { class: "field" }, "Mô hình", modSel),
      h("label", { class: "field" }, "Chu kỳ T (năm)", tInput),
      h("label", { class: "field" }, "hoặc lượng mưa (mm)", vInput),
      shareButton()),
    h("div", { class: "card", style: "margin-bottom:1rem" }, calcOut),
    tableCard.root, chartCard.root, cmpCard.root, fitCard.root);

  let ch = null;
  function draw() {
    setParams({ chuoi: key === "hour" ? "gio" : "ngay", mohinh: model, T: tInput.value || null });
    const s = ret.series[key];
    const unit = s.unit;
    const g = gridOf(s, model);
    const mLabel = MODELS.find((m) => m[0] === model)[2];
    const hasCI = model === "gumbel";
    const potCI = model === "pot" ? s.pot.ci_table : null;

    // Bảng kiểu PFDS
    const rows = ret.T_table.map((T) => {
      const i = G.indexOf(T);
      const ci = hasCI ? [s.ci.lo[i], s.ci.hi[i]] : potCI && potCI[T] ? potCI[T] : null;
      return { T, aep: 100 / T, est: g[i], lo: ci ? ci[0] : null, hi: ci ? ci[1] : null };
    });
    tableCard.root.querySelector(".card-head")?.remove();
    tableCard.body.replaceChildren(
      h("h3", {}, `${s.label} (${unit}) — ${mLabel}`),
      h("p", { class: "sub" }, hasCI ? "Ước lượng và khoảng tin cậy 95%" : potCI ? "Khoảng tin cậy 95% bootstrap cho T = 10–100 năm" : "Khoảng tin cậy chỉ tính cho mô hình chính (Gumbel) và POT"),
      dataTable([
        { key: "T", label: "Chu kỳ T (năm)", align: "left" },
        { key: "aep", label: "Xác suất vượt/năm", fmt: (v) => `${fmt(v, v < 1 ? 1 : 0)}%` },
        { key: "est", label: `Ước lượng (${unit.split("/")[0]})`, fmt: (v) => `<strong>${fmt(v, 1)}</strong>` },
        { key: "lo", label: "KTC 95% thấp", fmt: (v) => fmt(v, 1) },
        { key: "hi", label: "KTC 95% cao", fmt: (v) => fmt(v, 1) },
      ], rows, { csvName: `chu_ky_${key === "day" ? "ngay" : "gio"}_${model}.csv` }),
      caption(`Giá trị lớn nhất quan trắc: ${fmt(Math.max(...s.values.map((v) => v[1])), 1)} ${unit} (năm ${s.values.reduce((a, b) => (b[1] > a[1] ? b : a))[0]}).`));

    // Biểu đồ
    // Dải KTC vẽ thành một đa giác (cận dưới đi tới, cận trên đi về)
    const band = {
      name: "KTC 95% (Gumbel)", type: "custom", silent: true, z: 1, clip: true, tooltip: { show: false },
      itemStyle: { color: "rgba(156,195,217,.8)" },
      data: G.map((T, i) => [T, s.ci.hi[i]]).concat(G.map((T, i) => [T, s.ci.lo[i]])),
      encode: { x: 0, y: 1 },
      renderItem: (p, api) => {
        if (p.dataIndex !== 0) return null;
        const pts = G.map((T, i) => api.coord([T, s.ci.lo[i]])).concat(G.slice().reverse().map((T, k) => api.coord([T, s.ci.hi[G.length - 1 - k]])));
        return { type: "polygon", shape: { points: pts }, style: { fill: "rgba(156,195,217,.45)" } };
      },
    };
    const series = [
      band,
      ...MODELS.map(([id, , label]) => ({
        name: label, type: "line", showSymbol: false, data: G.map((T, i) => [T, gridOf(s, id)[i]]),
        lineStyle: { width: id === model ? 3 : 1.2, type: ["gumbel", "pot", "lmom"].includes(id) || id === model ? "solid" : "dashed", color: COLORS[id], opacity: id === model ? 1 : 0.75 },
        itemStyle: { color: COLORS[id] }, z: id === model ? 5 : 2,
      })),
      {
        name: "Quan trắc (Gringorten)", type: "scatter", symbolSize: 9, itemStyle: { color: C.ink }, z: 10,
        data: s.gringorten.map(([T, v, y]) => ({ value: [T, v], name: String(y) })),
        tooltip: { trigger: "item", formatter: (p) => `Năm ${p.name}: ${fmt(p.value[1], 1)} ${unit}<br>T kinh nghiệm ≈ ${fmt(p.value[0], 1)} năm` },
      },
    ];
    const opt = {
      tooltip: { trigger: "axis", formatter: (ps) => `T = ${fmt(ps[0].value[0], ps[0].value[0] < 10 ? 1 : 0)} năm<br>` + ps.filter((p) => p.seriesType === "line").map((p) => `${p.marker}${p.seriesName}: ${fmt(p.value[1], 1)}`).join("<br>") },
      legend: { type: "scroll", top: 0, left: 0, right: 40, data: [mLabel, ...MODELS.filter((m) => m[0] !== model).map((m) => m[2]), "Quan trắc (Gringorten)", "KTC 95% (Gumbel)"] },
      grid: { top: 56, bottom: 50 },
      xAxis: { type: "log", min: 1, max: 1000, ...axisName("Chu kỳ lặp lại T (năm)"), axisLabel: { formatter: (v) => fmt(v, 0) } },
      yAxis: { type: "value", ...axisName(unit, { nameGap: 48 }) },
      series,
    };
    if (!ch) ch = chart(chartEl, opt, { label: "Đường tần suất mưa cực đại" });
    else ch.setOption(opt, { replaceMerge: ["series"] });

    // So sánh mô hình
    cmpCard.body.replaceChildren(dataTable([
      { key: "label", label: "Phương án", align: "left" },
      ...ret.T_table.map((T) => ({ key: `t${T}`, label: `T = ${T}`, fmt: (v) => fmt(v, 1) })),
    ], MODELS.map(([id, , label]) => ({
      label: id === "pot" ? `${label} (u = ${fmt(s.pot.u, 1)} mm, ${s.pot.n_peaks} đợt, ξ = ${fmt(s.pot.xi, 3)})` :
        id === "drop" ? `${label} (${fmt(s.drop_max.value, 1)} mm năm ${s.drop_max.year})` : label + (MODELS.find((m) => m[0] === id)[1] === s.selected ? " — chọn" : ""),
      ...Object.fromEntries(ret.T_table.map((T) => [`t${T}`, gridOf(s, id)[G.indexOf(T)]])),
    })), { csvName: `so_sanh_mo_hinh_${key === "day" ? "ngay" : "gio"}.csv` }));

    // Chỉ tiêu phù hợp
    const minAIC = Math.min(...Object.values(s.models).map((m) => m.AIC));
    fitCard.body.replaceChildren(dataTable([
      { key: "name", label: "Phân bố", align: "left", fmt: (v) => `${v}${v === s.selected ? ' <span class="flag ok">chọn</span>' : ""}` },
      { key: "k", label: "Số tham số" },
      { key: "logL", label: "logL", fmt: (v) => fmt(v, 2) }, { key: "AIC", label: "AIC", fmt: (v) => (v === minAIC ? `<strong>${fmt(v, 2)}</strong>` : fmt(v, 2)) },
      { key: "BIC", label: "BIC", fmt: (v) => fmt(v, 2) }, { key: "KS", label: "KS", fmt: (v) => fmt(v, 3) },
      { key: "KS_p", label: "p (KS)", fmt: (v) => fmt(v, 2) }, { key: "CvM", label: "CvM", fmt: (v) => fmt(v, 3) }, { key: "AD", label: "AD", fmt: (v) => fmt(v, 3) },
    ], Object.entries(s.models).map(([name, m]) => ({ name, k: name === "GEV" ? 3 : 2, ...m })), { csvName: `chi_tieu_phu_hop_${key}.csv` }),
    caption("Giá trị AIC nhỏ nhất được in đậm. Với n = 10, các thống kê KS đều nhỏ hơn giá trị tới hạn 0,41 (mức 5%), tức không phân bố nào bị bác bỏ."));
    calc("T");
  }

  function calc(from) {
    const s = ret.series[key];
    const g = gridOf(s, model);
    const unit = s.unit;
    if (from === "T") {
      const T = parseFloat(tInput.value);
      if (!(T > 1 && T <= 1000)) { calcOut.textContent = "Nhập chu kỳ T trong khoảng 1,1–1000 năm."; return; }
      const v = levelAt(T, G, g);
      vInput.value = "";
      calcOut.replaceChildren(h("p", {}, `Với ${s.label}, mức mưa ứng với chu kỳ ${fmt(T, T < 10 ? 1 : 0)} năm (xác suất vượt ${fmt(100 / T, 2)}%/năm) theo ${MODELS.find((m) => m[0] === model)[2]} là `,
        h("strong", {}, `${fmt(v, 1)} ${unit}`), "."));
      setParams({ T });
    } else {
      const v = parseFloat(vInput.value);
      if (!(v > 0)) return;
      const T = periodOf(v, G, g);
      calcOut.replaceChildren(h("p", {}, `${fmt(v, 1)} ${unit} ứng với chu kỳ lặp lại `,
        h("strong", {}, T ? `khoảng ${fmt(T, T < 10 ? 1 : 0)} năm` : v < g[0] ? "dưới 1 năm" : "trên 1000 năm"),
        T ? ` (xác suất vượt khoảng ${fmt(100 / T, 2)}% mỗi năm).` : "."));
    }
  }

  serSel.addEventListener("change", () => { key = serSel.value; draw(); });
  modSel.addEventListener("change", () => { model = modSel.value; draw(); });
  tInput.addEventListener("input", () => calc("T"));
  vInput.addEventListener("input", () => calc("v"));
  draw();
}

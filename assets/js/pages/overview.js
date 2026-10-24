import { load } from "../data.js";
import { h, card, chartBox, caption, stats, notice } from "../components.js";
import { chart, C, axisName, markLines } from "../charts.js";
import { fmt, fmtInt, fmtDate, ROMAN, utcMs } from "../format.js";

export async function render(host) {
  const [meta, annual, monthly, rx, thr, ret, events, ls] =
    await load("meta", "annual", "monthly", "rx", "thresholds", "returns", "events", "landslide");

  const tA = annual.stats.total;
  const share = annual.stats.rainy_share;
  const maxRx = rx.rows.reduce((a, b) => (b.rx1day > a.rx1day ? b : a));
  const dSel = ret.series.day;
  const i100 = ret.T_grid.indexOf(100);
  const t100 = dSel.models[dSel.selected].grid[i100];
  const ev = events.events.find((e) => e.year === 2017);

  const hero = h("section", { class: "hero" },
    h("h1", {}, "Mưa giờ trạm Trà My, 2008–2017"),
    h("p", {}, "Tra cứu từng giờ, từng ngày mưa trong 10 năm quan trắc tại một trong những nơi mưa nhiều nhất Việt Nam; xem thống kê, mưa cực trị, ngưỡng mưa rất lớn và mức mưa thiết kế theo chu kỳ lặp lại."),
    h("div", { class: "hero-actions" },
      h("a", { class: "btn primary", href: "#/tra-cuu" }, "Tra cứu một ngày"),
      h("a", { class: "btn", href: "#/chu-ky" }, "Mưa theo chu kỳ lặp lại"),
      h("a", { class: "btn", href: "#/tai-du-lieu" }, "Tải dữ liệu")));

  const cards = stats([
    { label: "Lượng mưa năm trung bình", value: fmt(tA.mean, 0), unit: "mm", note: `${tA.n} năm đủ số liệu; ${fmt(tA.min, 0)}–${fmt(tA.max, 0)} mm` },
    { label: "Mùa mưa IX–XII đóng góp", value: fmt(share.mean, 0), unit: "%", note: "trung bình tổng lượng mưa năm", tone: "orange" },
    { label: "Mưa ngày lớn nhất", value: fmt(maxRx.rx1day, 1), unit: "mm", note: `ngày ${fmtDate(maxRx.rx1day_date)}`, tone: "orange" },
    { label: "Ngưỡng ngày mưa rất lớn R95p", value: fmt(thr.blocks.day_all.R95p, 1), unit: "mm", note: `R99p: ${fmt(thr.blocks.day_all.R99p, 1)} mm` },
    { label: "Mưa ngày chu kỳ 100 năm", value: fmt(t100, 0), unit: "mm", note: `phân bố ${dSel.selected}, n = 10 năm` },
    { label: "Ngày có trượt lở", value: fmtInt(ls.events.length), unit: "ngày", note: `${ls.events.filter((e) => e.gt_r95).length}/${ls.events.length} ngày mưa vượt R95p`, tone: "slide" },
  ]);

  const questions = h("div", { class: "questions" }, [
    ["Câu 1", "Thống kê", "Mưa giờ, ngày, tháng, năm và theo mùa", "#/thong-ke"],
    ["Câu 2", "Cực trị", "Rx1day, Rx5day, Rx1hour từng năm và các đợt mưa lớn", "#/cuc-tri"],
    ["Câu 3", "Ngưỡng R95p/R99p", "Ngưỡng mưa giờ, mưa ngày rất lớn và cực kỳ lớn", "#/nguong"],
    ["Câu 4", "Chu kỳ lặp lại", "Mưa giờ, mưa ngày ứng với 10, 20, 50, 100 năm", "#/chu-ky"],
  ].map(([q, t, s, href]) => h("a", { class: "question", href }, h("span", { class: "q" }, q), h("strong", {}, t), h("span", {}, s))));

  // Bản đồ + khí hậu tháng
  const mapCard = card("Vị trí trạm", { sub: `${meta.station}, ${meta.province}. ${meta.location_note}.` });
  const mapEl = h("div", { id: "map", role: "img", "aria-label": "Bản đồ vị trí trạm Trà My" });
  mapCard.body.append(mapEl);
  const climCard = card("Lượng mưa trung bình theo tháng", { sub: "Tháng hợp lệ 2008–2017; cột cam là mùa mưa IX–XII" });
  const climEl = chartBox();
  climCard.body.append(climEl, caption("Nguồn: data/monthly.json"));

  // Câu chuyện: đợt mưa 11/2017
  const evCard = card(`Đợt mưa lớn nhất: ${fmtDate(ev.window[0])}–${fmtDate(ev.window[1])}`, {
    sub: `Tổng 5 ngày ${fmt(ev.total, 1)} mm; riêng ngày 05/11/2017 mưa ${fmt(maxRx.rx1day, 1)} mm. Vùng đỏ nhạt: giờ có ghi nhận trượt lở.`,
    actions: [h("a", { class: "btn small", href: "#/cuc-tri?nam=2017" }, "Xem chi tiết")],
  });
  const evEl = chartBox();
  evCard.body.append(evEl);

  // Câu chuyện: mưa và trượt lở
  const lsCard = card("Mưa và trượt lở đất", {
    sub: `Lượng mưa ngày của ${ls.events.length} ngày có trượt lở so với ngưỡng R95p (${fmt(ls.R95p_day, 1)} mm) và R99p (${fmt(ls.R99p_day, 1)} mm)`,
    actions: [h("a", { class: "btn small", href: "#/truot-lo" }, "Phân tích trượt lở")],
  });
  const lsEl = chartBox();
  lsCard.body.append(lsEl);

  host.replaceChildren(
    hero, cards,
    h("h2", {}, "Bốn câu hỏi phân tích"), questions,
    h("div", { class: "grid grid-2" }, mapCard.root, climCard.root),
    h("h2", {}, "Những điều đáng chú ý"),
    notice("Mùa mưa IX–XII chiếm khoảng hai phần ba lượng mưa năm; tháng XI mưa nhiều nhất. Các ngày mưa lớn nhất mỗi năm đều rơi vào mùa này và phần lớn trùng với ngày xảy ra trượt lở."),
    h("div", { class: "grid grid-2" }, evCard.root, lsCard.root));

  // Bản đồ Leaflet: nền Esri mặc định (tile.openstreetmap.org không truy cập được từ một số mạng ở Việt Nam)
  if (window.L) {
    const L = window.L;
    const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    const esri = (name) => `https://server.arcgisonline.com/ArcGIS/rest/services/${name}/MapServer/tile/{z}/{y}/{x}`;
    const layers = {
      "Đường phố (Esri)": L.tileLayer(esri("World_Street_Map"), { maxZoom: 18, attribution: "Tiles &copy; Esri" }),
      "Địa hình (Esri)": L.tileLayer(esri("World_Topo_Map"), { maxZoom: 18, attribution: "Tiles &copy; Esri" }),
      "Địa hình (OpenTopoMap)": L.tileLayer("https://tile.opentopomap.org/{z}/{x}/{y}.png", {
        maxZoom: 17, attribution: `${osmAttr}, SRTM | Kiểu bản đồ &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)`,
      }),
      "OpenStreetMap": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: osmAttr }),
    };
    const map = L.map(mapEl, { scrollWheelZoom: false, layers: [layers["Đường phố (Esri)"]] }).setView([meta.lat, meta.lon], 9);
    L.control.layers(layers, null, { collapsed: true }).addTo(map);
    window.L.marker([meta.lat, meta.lon]).addTo(map)
      .bindPopup(`<strong>${meta.station}</strong><br>Lượng mưa năm TB: ${fmt(tA.mean, 0)} mm<br><a href="#/tra-cuu">Tra cứu số liệu</a>`).openPopup();
  }

  const clim = monthly.climatology;
  chart(climEl, {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: clim.map((c) => ROMAN[c.month]), ...axisName("Tháng") },
    yAxis: { type: "value", ...axisName("mm", { nameGap: 48 }) },
    series: [{
      name: "Trung bình tháng", type: "bar",
      data: clim.map((c) => ({ value: c.mean, itemStyle: { color: c.month >= 9 ? C.orange : C.rain } })),
    }],
  }, { label: "Biểu đồ lượng mưa trung bình theo tháng" });

  const times = ev.rain.map((_, i) => i);
  const startMs = utcMs(ev.start);
  const t = (i) => startMs + (i + 1) * 3600000;
  let cum = 0;
  const w0 = (utcMs(ev.window[0]) - startMs) / 3600000;
  const cumData = times.map((i) => {
    if (i < w0 || i >= w0 + 120) return [t(i), null];
    cum += ev.rain[i] || 0;
    return [t(i), +cum.toFixed(1)];
  });
  chart(evEl, {
    tooltip: { trigger: "axis" },
    legend: { top: 0, left: 0 },
    xAxis: { type: "time", axisLabel: { formatter: "{dd}/{MM}" } },
    yAxis: [{ type: "value", name: "mm/giờ" }, { type: "value", name: "Tích lũy (mm)", splitLine: { show: false } }],
    series: [
      {
        name: "Mưa giờ", type: "bar", barWidth: "90%", data: times.map((i) => [t(i), ev.rain[i]]), itemStyle: { color: C.rain },
        markArea: { silent: true, itemStyle: { color: "rgba(122,31,31,.12)" }, data: ev.slide.map((i) => [{ xAxis: t(i - 1) }, { xAxis: t(i) }]) },
      },
      { name: "Lũy kế 5 ngày", type: "line", yAxisIndex: 1, showSymbol: false, data: cumData, lineStyle: { color: C.orange, width: 2.5 }, itemStyle: { color: C.orange } },
    ],
  }, { label: "Biểu đồ mưa giờ và lượng tích lũy đợt mưa tháng 11 năm 2017" });

  const evs = ls.events;
  chart(lsEl, {
    tooltip: { trigger: "item", formatter: (p) => `${fmtDate(p.name)}<br>Mưa ngày: ${fmt(p.value, 1)} mm` },
    xAxis: { type: "category", data: evs.map((e) => e.date), axisLabel: { formatter: (v) => fmtDate(v).slice(0, 5) + "\n" + v.slice(0, 4), fontSize: 10 } },
    yAxis: { type: "value", name: "mm/ngày" },
    series: [{
      type: "bar", data: evs.map((e) => ({ value: e.rain, name: e.date, itemStyle: { color: e.gt_r99 ? C.slide : e.gt_r95 ? C.orange : C.soft } })),
      markLine: markLines([[ls.R95p_day, C.gold, "R95p"], [ls.R99p_day, C.slide, "R99p"]]),
    }],
  }, { label: "Lượng mưa ngày của các ngày có trượt lở" });
}

import { load } from "../data.js";
import { h, card, pageHead, notice } from "../components.js";
import { fmt, fmtInt } from "../format.js";

export async function render(host) {
  const [meta, summary] = await load("meta", "summary");
  const q = summary.qc;

  const data = card("Dữ liệu", {});
  data.body.append(
    h("p", { html: `Chuỗi lượng mưa giờ tại <strong>${meta.station}</strong> (${meta.province}), từ 01/01/2008 đến 31/12/2017: ${fmtInt(q.hours)} bản ghi giờ (${fmtInt(q.days)} ngày, đủ 24 giờ mỗi ngày, không trùng lặp), độ phân giải 0,1 mm. Kèm theo cờ ghi nhận trượt lở đất theo giờ.` }),
    h("p", { html: `Quy ước giờ: ${meta.rules.hour_convention}; lượng mưa ngày là tổng 24 giờ của ngày đó. Mùa mưa: tháng IX–XII; mùa khô: tháng I–VIII.` }),
    notice("Đề bài gốc nêu số liệu hai trạm giai đoạn 2011–2020; tệp số liệu thực tế chỉ có một trạm Trà My giai đoạn 2008–2017 (vẫn đủ 10 năm). Mọi phân tích dùng thời đoạn thực tế này."));

  const qc = card("Kiểm tra chất lượng và xử lý", {});
  qc.body.append(h("ul", {},
    h("li", { html: `Thiếu ${fmtInt(q.hours_missing)} giờ (${fmt((100 * q.hours_missing) / q.hours, 1)}%). Thiếu kéo dài: toàn bộ tháng 11/2009 và phần lớn tháng 01/2017; ngoài ra phần lớn ngày mùng 1 hằng tháng thiếu số liệu.` }),
    h("li", { html: `<strong>Ngày hợp lệ</strong>: có ít nhất ${meta.rules.valid_day_hours}/24 giờ có số liệu (${fmtInt(q.days_ok)}/${fmtInt(q.days)} ngày).` }),
    h("li", { html: `<strong>Tháng hợp lệ</strong>: có ít nhất ${meta.rules.valid_month_frac * 100}% số ngày hợp lệ (${q.months_ok}/${q.months} tháng).` }),
    h("li", { html: "<strong>Năm, mùa hợp lệ</strong>: mọi tháng trong năm (mùa) đều hợp lệ; nếu không, tổng năm (mùa) vẫn hiển thị nhưng không đưa vào thống kê." }),
    h("li", { html: "Chuỗi cực trị năm (Rx1day, Rx5day, Rx1hour) dùng đủ 10 năm (tỉ lệ ngày hợp lệ thấp nhất 89,6% năm 2009)." })));

  const defs = card("Định nghĩa chỉ số", {});
  defs.body.append(h("dl", { class: "defs" }, [
    ["Ngày (giờ) mưa", "Lượng mưa ≥ 1 mm (theo ETCCDI)."],
    ["CV", "Hệ số biến thiên = độ lệch chuẩn / trung bình × 100%."],
    ["Độ lệch", "Hệ số bất đối xứng Fisher–Pearson hiệu chỉnh; dương nghĩa là phân bố lệch phải."],
    ["Rx1day", "Lượng mưa ngày lớn nhất trong năm."],
    ["Rx5day", "Tổng lượng mưa lớn nhất của 5 ngày liên tiếp trong năm (tổng trượt 5 ngày)."],
    ["Rx1hour", "Lượng mưa giờ lớn nhất trong năm."],
    ["R95p, R99p", "Phân vị 95% và 99% của lượng mưa các ngày (giờ) mưa trong thời kỳ cơ sở 2008–2017; vượt R95p là rất lớn, vượt R99p là cực kỳ lớn."],
    ["Chu kỳ lặp lại T", "Khoảng thời gian trung bình giữa hai lần lượng mưa cực đại năm vượt một mức; xác suất vượt mỗi năm = 1/T."],
  ].flatMap(([t, d]) => [h("dt", {}, t), h("dd", {}, d)])));

  const freq = card("Phân tích tần suất", {});
  freq.body.append(
    h("p", { html: "Chuỗi cực đại năm (n = 10) được khớp 5 phân bố bằng phương pháp hợp lý cực đại (<code>scipy.stats</code>): Gumbel, GEV, chuẩn loga 2 tham số, Gamma, Weibull. Mức độ phù hợp đánh giá bằng AIC = 2k − 2 ln L, BIC = k ln n − 2 ln L, và các thống kê Kolmogorov–Smirnov, Cramér–von Mises, Anderson–Darling." }),
    h("p", { html: 'Mức mưa theo phân bố Gumbel: <span class="formula">x<sub>T</sub> = μ − β · ln[−ln(1 − 1/T)]</span>. Chọn phân bố hai tham số có AIC nhỏ nhất; nếu chênh lệch so với Gumbel nhỏ hơn 2 thì chọn Gumbel. Cả mưa giờ và mưa ngày đều chọn Gumbel.' }),
    h("p", { html: "Khoảng tin cậy 95%: bootstrap tham số 2000 lần (sinh mẫu cỡ 10 từ phân bố đã khớp, khớp lại, lấy phân vị 2,5% và 97,5%). Tần suất kinh nghiệm theo công thức Gringorten F = (i − 0,44)/(n + 0,12)." }),
    h("p", { html: 'Phân tích độ nhạy dùng thêm Gumbel ước lượng bằng L-moment, phương pháp vượt ngưỡng POT với phân bố Pareto tổng quát (ngưỡng R95p, tách đợt độc lập cách nhau 24 giờ hoặc 3 ngày; <span class="formula">x<sub>T</sub> = u + σ/ξ · [(λT)<sup>ξ</sup> − 1]</span>) và Gumbel khi bỏ giá trị lớn nhất.' }));

  const refs = card("Tài liệu tham khảo", {});
  refs.body.append(h("ol", {}, [
    "Zhang, X. et al. (2011). Indices for monitoring changes in extremes based on daily temperature and precipitation data. WIREs Climate Change, 2(6), 851–870.",
    'Climdex — ETCCDI Climate Change Indices. <a href="https://www.climdex.org/learn/indices/">climdex.org/learn/indices</a>',
    'NOAA Atlas 14 — Precipitation Frequency Data Server. <a href="https://hdsc.nws.noaa.gov/pfds/">hdsc.nws.noaa.gov/pfds</a>',
    "Hosking, J. R. M. (1990). L-moments: analysis and estimation of distributions using linear combinations of order statistics. JRSS B, 52(1), 105–124.",
    "Coles, S. (2001). An Introduction to Statistical Modeling of Extreme Values. Springer.",
    "Gringorten, I. I. (1963). A plotting rule for extreme probability paper. Journal of Geophysical Research, 68(3), 813–814.",
    "Akaike, H. (1974). A new look at the statistical model identification. IEEE Transactions on Automatic Control, 19(6), 716–723.",
    "Stephens, M. A. (1974). EDF statistics for goodness of fit and some comparisons. JASA, 69(347), 730–737.",
  ].map((t) => h("li", { html: t }))));

  const about = card("Giới thiệu", {});
  about.body.append(
    h("p", { html: "Website được xây dựng từ bài phân tích số liệu mưa giờ trạm Trà My. Thực hiện: <strong>Dương Quang Huy</strong>, ngành Khoa học dữ liệu, khóa 68. Giáo viên hướng dẫn: <strong>GS. Đỗ Văn Đức</strong>." }),
    h("p", { html: "Công nghệ: HTML, CSS, JavaScript (không cần máy chủ), biểu đồ Apache ECharts, bản đồ Leaflet và OpenStreetMap; dữ liệu tính bằng Python (pandas, numpy, scipy); triển khai tự động lên GitHub Pages bằng GitHub Actions." }));

  host.replaceChildren(
    pageHead("Phương pháp", "Phương pháp và giới thiệu", "Cách số liệu được kiểm tra, các chỉ số được tính và nguồn tham khảo."),
    h("div", { class: "grid grid-2" }, data.root, qc.root),
    defs.root, freq.root,
    h("div", { class: "grid grid-2" }, refs.root, about.root));
}

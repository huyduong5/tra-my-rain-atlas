import { getJSON, load } from "../data.js";
import { h, card, pageHead, notice } from "../components.js";
import { fmt } from "../format.js";
import { SITE } from "../routes.js";

const size = (b) => (b > 1048576 ? `${fmt(b / 1048576, 1)} MB` : `${fmt(b / 1024, 1)} KB`);

export async function render(host) {
  const [{ files }, [meta]] = await Promise.all([getJSON("files.json"), load("meta")]);
  const list = card("Các tệp dữ liệu", { sub: "CSV mở được bằng Excel (mã hóa UTF-8, dấu phẩy phân cách); JSON dùng cho lập trình" });
  const rows = files.map((f) => h("tr", {},
    h("td", { class: "left" }, h("strong", {}, f.title), h("br"), h("span", { class: "sub", style: "color:var(--muted);font-size:.85rem;white-space:normal" }, f.desc)),
    h("td", {}, f.type),
    h("td", {}, size(f.size)),
    h("td", {}, f.path.endsWith("/")
      ? h("a", { class: "btn small", href: `${SITE.repo}/tree/main/${f.path}` }, "Xem trên GitHub")
      : h("a", { class: "btn small primary", href: f.path, download: "" }, "Tải về"))));
  list.body.append(h("div", { class: "table-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, h("th", { class: "left" }, "Nội dung"), h("th", {}, "Định dạng"), h("th", {}, "Dung lượng"), h("th", {}, ""))),
    h("tbody", {}, rows))));

  const src = card("Mã nguồn và tái lập kết quả", {});
  src.body.append(
    h("p", { html: `Toàn bộ mã nguồn website và chương trình phân tích (Python) nằm trên GitHub: <a href="${SITE.repo}">${SITE.repo.replace("https://", "")}</a>.` }),
    h("ol", {},
      h("li", { html: "Cài Python 3.12 và các thư viện <code>pandas numpy scipy matplotlib</code>." }),
      h("li", { html: "Chạy <code>python3 scripts/build_data.py</code> để tính lại toàn bộ dữ liệu trong thư mục <code>data/</code>." }),
      h("li", { html: "Chạy <code>python3 scripts/validate_data.py</code> để kiểm tra số liệu khớp với báo cáo." }),
      h("li", { html: "Xem website trên máy: <code>python3 -m http.server 8000</code> rồi mở <code>http://localhost:8000</code>." })));

  host.replaceChildren(
    pageHead("Dữ liệu mở", "Tải dữ liệu",
      `Số liệu mưa giờ trạm Trà My ${meta.period.map((d) => d.split("-").reverse().join("/")).join(" – ")} và các kết quả tính toán của website. Dữ liệu được tạo lúc ${meta.generated}.`),
    list.root,
    notice("Khi sử dụng lại số liệu, vui lòng ghi rõ nguồn: “Trà My Rain Atlas — số liệu mưa giờ trạm Trà My 2008–2017” và đơn vị cung cấp số liệu gốc."),
    src.root);
}

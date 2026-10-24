// Điều hướng bằng hash: #/duong-dan?thamso=giatri
import { ROUTES, SITE } from "./routes.js";
import { disposeAll } from "./charts.js";
import { h, notice } from "./components.js";

export function parseHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
  const [path, qs = ""] = raw.split("?");
  return { path: path.replace(/\/$/, ""), params: Object.fromEntries(new URLSearchParams(qs)) };
}

export function buildHash(path, params = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, v);
  const qs = q.toString();
  return `#/${path}${qs ? `?${qs}` : ""}`;
}

/** Cập nhật tham số trên URL mà không vẽ lại trang (để chia sẻ link) */
export function setParams(params) {
  const { path, params: cur } = parseHash();
  history.replaceState(null, "", buildHash(path, { ...cur, ...params }));
}

export function go(path, params = {}) {
  location.hash = buildHash(path, params);
}

let token = 0;
// Mã phiên bản do CI điền vào index.html, giúp trình duyệt tải trang mới sau mỗi lần triển khai
const BUILD = document.querySelector('meta[name="build"]')?.content || "dev";

export async function render() {
  const main = document.getElementById("main");
  const { path, params } = parseHash();
  const route = ROUTES.find((r) => r.path === path);
  document.querySelectorAll(".site-nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.path === (route ? route.path : null));
    if (a.dataset.path === (route ? route.path : null)) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.getElementById("site-nav").classList.remove("open");
  document.querySelector(".nav-toggle").setAttribute("aria-expanded", "false");

  disposeAll();
  const my = ++token;
  if (!route) {
    document.title = `Không tìm thấy trang — ${SITE.name}`;
    main.replaceChildren(h("h1", {}, "Không tìm thấy trang"),
      notice(`Đường dẫn <code>#/${path}</code> không tồn tại. <a href="#/">Về trang Tổng quan</a>.`, "warn"));
    return;
  }
  document.title = route.path ? `${route.title} — ${SITE.name}` : `${SITE.name} — Tra cứu và phân tích mưa giờ trạm Trà My`;
  // Khung trang được gắn vào DOM trước để biểu đồ đo được kích thước
  const host = h("div", {}, h("p", { class: "loading" }, "Đang tải dữ liệu…"));
  main.replaceChildren(host);
  window.scrollTo({ top: 0 });
  try {
    const mod = await import(`./pages/${route.module}.js?v=${BUILD}`);
    if (my !== token) return;
    await mod.render(host, params, () => my === token);
  } catch (err) {
    console.error(err);
    if (my !== token) return;
    main.replaceChildren(h("h1", {}, route.title),
      notice(`Không hiển thị được trang này: ${err.message}. Hãy tải lại trang (F5).`, "error"));
  }
}

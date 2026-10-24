import { ROUTES, SITE } from "./routes.js";
import { render } from "./router.js";
import { h } from "./components.js";

// Đường dẫn repo suy ra từ địa chỉ GitHub Pages (<owner>.github.io/tra-my-rain-atlas)
if (location.hostname.endsWith("github.io")) {
  SITE.repo = `https://github.com/${location.hostname.split(".")[0]}/tra-my-rain-atlas`;
}
document.getElementById("repo-link").href = SITE.repo;

const nav = document.getElementById("site-nav");
for (const r of ROUTES) {
  nav.append(h("a", { href: `#/${r.path}`, "data-path": r.path }, r.title, r.badge ? h("span", { class: "badge" }, r.badge) : null));
}
const toggle = document.querySelector(".nav-toggle");
toggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});

window.addEventListener("hashchange", render);
if (!window.echarts) {
  document.getElementById("main").innerHTML =
    '<div class="notice error">Không tải được thư viện biểu đồ (vendor/echarts.min.js).</div>';
} else {
  render();
}

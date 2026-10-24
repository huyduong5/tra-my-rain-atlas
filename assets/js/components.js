// Thành phần giao diện dùng chung
/** Tạo phần tử: h("div", {class: "card"}, child1, "text") */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function pageHead(kicker, title, lead) {
  return h("header", { class: "page-head" },
    kicker ? h("span", { class: "kicker" }, kicker) : null,
    h("h1", {}, title),
    lead ? h("p", { class: "lead", html: lead }) : null);
}

/** Thẻ có tiêu đề, phụ đề, các nút hành động */
export function card(title, { sub, actions = [], cls = "" } = {}) {
  const body = h("div", { class: "card-body" });
  const root = h("section", { class: `card ${cls}` },
    title ? h("div", { class: "card-head" },
      h("div", { class: "titles" }, h("h3", {}, title), sub ? h("p", { class: "sub", html: sub }) : null),
      actions.length ? h("div", { class: "card-actions" }, actions) : null) : null,
    body);
  return { root, body };
}

export function chartBox(cls = "") {
  return h("div", { class: `chart ${cls}` });
}

export function caption(text) {
  return h("p", { class: "caption", html: text });
}

/** Danh sách thẻ số liệu: [{label, value, unit, note, tone}] */
export function stats(items) {
  return h("div", { class: "stats" }, items.map((s) =>
    h("div", { class: `stat ${s.tone || ""}` },
      h("div", { class: "label" }, s.label),
      h("div", { class: "value" }, s.value, s.unit ? h("span", { class: "unit" }, s.unit) : null),
      s.note ? h("div", { class: "note", html: s.note }) : null)));
}

export function notice(html, tone = "") {
  return h("div", { class: `notice ${tone}`, role: tone === "error" ? "alert" : null, html });
}

/** Thuật ngữ có định nghĩa hiện khi rê chuột hoặc focus */
export function term(text, def) {
  return `<span class="term" tabindex="0" data-def="${def.replace(/"/g, "&quot;")}">${text}</span>`;
}

export function tabs(items, active, onChange) {
  const wrap = h("div", { class: "tabs", role: "tablist" });
  for (const [id, label] of items) {
    wrap.append(h("button", {
      class: "tab", role: "tab", "aria-selected": String(id === active), type: "button",
      onclick: () => {
        wrap.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", "false"));
        wrap.querySelector(`[data-id="${id}"]`).setAttribute("aria-selected", "true");
        onChange(id);
      },
      "data-id": id,
    }, label));
  }
  return wrap;
}

export function downloadText(filename, text, mime = "text/csv;charset=utf-8") {
  const blob = new Blob(["\ufeff" + text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function toCSV(columns, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map((c) => esc(c.label)).join(","),
    ...rows.map((r) => columns.map((c) => esc(c.csv ? c.csv(r) : r[c.key])).join(","))].join("\n");
}

/**
 * Bảng dữ liệu: columns [{key, label, fmt?, align?, sortable?, csv?}]
 * Tùy chọn: search (bool), csvName, onRowClick, rowClass
 */
export function dataTable(columns, rows, { search = false, csvName, onRowClick, rowClass, maxHeight } = {}) {
  let view = rows.slice();
  let sortKey = null;
  let sortDir = 1;
  const tbody = h("tbody");
  const thead = h("thead", {}, h("tr", {}, columns.map((c) => {
    const th = h("th", { class: `${c.align === "left" ? "left" : ""} ${c.sortable === false ? "" : "sortable"}`, scope: "col" }, c.label);
    if (c.sortable !== false) {
      th.addEventListener("click", () => {
        sortDir = sortKey === c.key ? -sortDir : 1;
        sortKey = c.key;
        thead.querySelectorAll("th").forEach((t) => t.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", sortDir > 0 ? "ascending" : "descending");
        view.sort((a, b) => {
          const x = a[c.key], y = b[c.key];
          if (x === y) return 0;
          if (x === null || x === undefined) return 1;
          if (y === null || y === undefined) return -1;
          return (x > y ? 1 : -1) * sortDir;
        });
        draw();
      });
    }
    return th;
  })));
  function draw() {
    tbody.replaceChildren(...view.map((r) => {
      const tr = h("tr", { class: `${onRowClick ? "clickable" : ""} ${rowClass ? rowClass(r) : ""}`, tabindex: onRowClick ? "0" : null },
        columns.map((c) => h("td", { class: c.align === "left" ? "left" : "", html: c.fmt ? c.fmt(r[c.key], r) : (r[c.key] ?? "—") })));
      if (onRowClick) {
        tr.addEventListener("click", () => onRowClick(r));
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter") onRowClick(r); });
      }
      return tr;
    }));
  }
  draw();
  const table = h("table", { class: "data" }, thead, tbody);
  const tools = h("div", { class: "table-tools" });
  if (search) {
    const input = h("input", { type: "search", placeholder: "Lọc nhanh…", "aria-label": "Lọc bảng" });
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      view = rows.filter((r) => !q || columns.some((c) => String(c.fmt ? c.fmt(r[c.key], r) : r[c.key] ?? "").toLowerCase().includes(q)));
      draw();
    });
    tools.append(input);
  }
  if (csvName) {
    tools.append(h("button", { class: "btn small", type: "button", onclick: () => downloadText(csvName, toCSV(columns, view)) }, "Tải CSV"));
  }
  const wrap = h("div", { class: "table-wrap", style: maxHeight ? `max-height:${maxHeight};overflow:auto` : null }, table);
  return h("div", {}, tools.childNodes.length ? tools : null, wrap);
}

export function shareButton() {
  return h("button", {
    class: "btn small", type: "button",
    onclick: async (e) => {
      try {
        await navigator.clipboard.writeText(location.href);
        e.target.textContent = "Đã sao chép liên kết";
      } catch {
        e.target.textContent = location.href;
      }
      setTimeout(() => { e.target.textContent = "Sao chép liên kết"; }, 2500);
    },
  }, "Sao chép liên kết");
}

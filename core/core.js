// ez-cognition core.
//
// The core knows nothing about tasks. It gives the modules four things:
// a registry, a page shell (a sidebar with a tree of contents, and the
// record), the personal state, and a refresh when a record changes.
// Everything that the page shows comes from a module in /modules/. The core
// must still run with no module.
//
// One page shows all the projects on this computer. A project has one or
// more tasks; the page shows one task at a time.
//
// A module is a folder with a module.js that imports this file and registers
// what it adds:
//
//   registry.add("panel", { id, order, title(task), summary(task), render(task, el), when(task),
//                           toc(task), tocNote(task), slot })   // see "page" below
//   registry.add("annotator", { id, apply(root, record) })  // marks text in a part of the page
//
// A module can define its own kind and let other modules add to it. The
// steps module does this with "step-part".
//
// Text in a record is Markdown (see md.js). Images live in the project's
// cognition-data/media/ folder and are written as "media/<file>". A link to
// a file of the project is its path from the project root, for example
// [split.py](src/split.py#L20-L40); the page opens it in the file viewer.

import { markdown, inline as mdInline, figure as mdFigure } from "/core/md.js";

// ---------- registry ----------

const kinds = new Map();

export const registry = {
  add(kind, item) {
    const list = kinds.get(kind) ?? [];
    const at = list.findIndex((other) => other.id === item.id);
    if (at >= 0) list[at] = item;
    else list.push(item);
    list.sort((a, b) => (a.order ?? 100) - (b.order ?? 100) || String(a.id).localeCompare(String(b.id)));
    kinds.set(kind, list);
  },
  list(kind) {
    return [...(kinds.get(kind) ?? [])];
  },
};

// ---------- small tools for modules ----------

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false || kid === "") continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

// ---------- text from a record ----------

const MEDIA = /^media\/(?!.*\.\.)[\w\-./]+\.(png|jpe?g|gif|webp|svg)$/i;

function imageURL(src) {
  if (!MEDIA.test(String(src)) || !app.projectId) return null;
  return `/files/${encodeURIComponent(app.projectId)}/${src.split("/").map(encodeURIComponent).join("/")}`;
}

// A file or folder of the project: "src/split.py#L20-L40", "docs/task.pdf#page=3",
// "results/". Not hidden, not outside the project.
const LOCAL = /^(?![/.])(?!.*(^|\/)\.)(?!.*\\)[^:*?"<>|]+$/;
const RAW = /\.(pdf|png|jpe?g|gif|webp|svg)$/i;

// The address that shows a file of the open project: the browser shows a PDF
// or an image itself; the file viewer shows the rest. Null when the path may
// not be shown.
export function fileURL(target) {
  const text = String(target ?? "");
  const at = text.indexOf("#");
  const path = at < 0 ? text : text.slice(0, at);
  const hash = at < 0 ? "" : text.slice(at);
  if (!LOCAL.test(path) || !app.projectId) return null;
  const parts = path.split("/").filter(Boolean);
  if (!path.endsWith("/") && RAW.test(path)) {
    return `/raw/${encodeURIComponent(app.projectId)}/${parts.map(encodeURIComponent).join("/")}${hash}`;
  }
  const query = new URLSearchParams({ project: app.projectId, path });
  return `/core/view.html?${query}${hash}`;
}

const TEXT = { image: imageURL, link: fileURL };

// One line of Markdown: bold, italic, code, links, math.
export function rich(text) {
  return mdInline(text, TEXT);
}

// Blocks of Markdown: paragraphs, lists, tables, headings, images.
export function md(text) {
  return markdown(text, TEXT);
}

// "原文 ↗" after a heading: the place in the source, a file of the project
// (a PDF opens at its page) or a web page.
export function source(link) {
  if (!link) return null;
  const url = /^https?:\/\//i.test(link) ? link : fileURL(link);
  if (!url) return null;
  return h("a", { class: "source-link", href: url, target: "_blank", rel: "noopener noreferrer", title: link }, t("core.source", "原文"), " ↗");
}

// An image from a record: { src: "media/x.png", alt }.
export function picture(image) {
  return image?.src ? mdFigure(image.src, image.alt ?? "", { image: imageURL }) : null;
}

export function points(list) {
  return h("ul", { class: "points" }, (list ?? []).map((line) => h("li", null, rich(line))));
}

// A card: a title, Markdown text, and an image in the text, under it (like
// an image in a README). A card is one part of the page for the
// annotators. With an `id`, the card is an entry of the tree of contents.
export function card({ title, text, image, notes: extra, link }, cls = "", id = null) {
  return h(
    "article",
    { class: `card${cls ? " " + cls : ""}`, "data-scope": "", id, "data-toc": id ? "" : null },
    h(
      "div",
      { class: "card-text" },
      title && h("h3", { class: "card-title" }, rich(title), source(link)),
      md(text),
      picture(image),
      notes(extra),
    ),
  );
}

// Run the annotators on each new part of the page, then render the math.
const annotated = new WeakSet();

export function finish(root) {
  if (!root) return;
  const scopes = [...root.querySelectorAll("[data-scope]")];
  if (root.matches?.("[data-scope]")) scopes.unshift(root);
  for (const scope of scopes) {
    if (annotated.has(scope)) continue;
    annotated.add(scope);
    for (const annotator of registry.list("annotator")) {
      try {
        annotator.apply(scope, app.task);
      } catch {
        // An annotator must not break the page.
      }
    }
  }
  typeset(root);
}

// Math: Temml turns TeX into MathML, which every current browser shows. It
// loads only when a page has math.
let temml = null;

async function typeset(root) {
  const nodes = [...root.querySelectorAll(".math:not([data-done])")];
  if (!nodes.length) return;
  try {
    temml ??= new Promise((done, fail) => {
      document.head.append(h("link", { rel: "stylesheet", href: "/core/vendor/temml/Temml-Local.css" }));
      document.head.append(h("script", { src: "/core/vendor/temml/temml.min.js", onload: () => done(window.temml), onerror: fail }));
    });
    const lib = await temml;
    for (const node of nodes) {
      node.dataset.done = "1";
      const tex = node.dataset.tex;
      try {
        node.replaceChildren();
        lib.render(tex, node, { displayMode: node.classList.contains("math-block"), throwOnError: false });
      } catch {
        node.textContent = tex;
      }
    }
  } catch {
    // Without the library, the TeX stays as text.
  }
}

// A short signature of a value. It changes when the value changes.
export function sig(value) {
  const text = JSON.stringify(value) ?? "";
  let hash = 5381;
  for (let i = 0; i < text.length; i++) hash = ((hash * 33) ^ text.charCodeAt(i)) >>> 0;
  return hash.toString(36);
}

// Interface text. Modules give the Chinese text; a locale file can replace it.
let locale = {};
export function t(key, zh) {
  return locale[key] ?? zh;
}

// ---------- state ----------

const app = {
  manifest: { projects: [], focus: null, modules: [], themes: [], locales: [] },
  user: { name: "", theme: "auto", motion: true, language: "zh", notes: false },
  view: {},
  projectId: null,
  taskId: null,
  task: null,
  problems: [],
  failed: [],
  online: false,
  updated: null,
};

export const user = () => ({ ...app.user });
export const manifest = () => app.manifest;
export const project = () => app.manifest.projects.find((p) => p.id === app.projectId) ?? null;

// The last `open` that this tab followed. A new tab follows the newest one.
const FOCUS_KEY = "ezc-focus";
let focusSeen = 0;
try {
  focusSeen = Number(sessionStorage.getItem(FOCUS_KEY) || 0);
} catch {
  // No session storage: the tab follows every `open`.
}

let pending = {};
let pendingProject = null;
let timer = null;

async function flush() {
  clearTimeout(timer);
  if (!Object.keys(pending).length) return;
  const body = { ...pending, project: pendingProject };
  pending = {};
  try {
    await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-EZC": "1" },
      body: JSON.stringify(body),
    });
  } catch {
    // The server stopped. The status line tells the user.
  }
}

function save(patch) {
  if (pendingProject !== app.projectId) flush();
  pendingProject = app.projectId;
  Object.assign(pending, patch);
  clearTimeout(timer);
  timer = setTimeout(flush, 200);
}

export function saveUser(patch, redraw = false) {
  Object.assign(app.user, patch);
  save({ user: { ...app.user } });
  applyUser();
  if (redraw) render();
}

// The personal state of the open task: what is folded, what the user marked.
export const state = {
  get(key, fallback) {
    const value = (app.view[app.taskId] ?? {})[key];
    return value === undefined ? fallback : value;
  },
  set(key, value) {
    if (!app.taskId) return;
    app.view[app.taskId] = { ...(app.view[app.taskId] ?? {}), [key]: value };
    save({ view: app.view });
  },
};

// ---------- folding ----------

// A line that opens and closes. `head` is always visible, so a closed fold
// still says something. `body(el)` fills the inside the first time it opens.
export function fold({ key, open = false, cls = "", head, body }) {
  const stored = state.get("open", {});
  let isOpen = key in stored ? stored[key] : open;
  let filled = false;
  const mark = h("span", { class: "mark" });
  const inside = h("div", { class: "fold-body" });
  const button = h("button", { class: "fold-head", type: "button", onclick: toggle }, mark, head);
  const el = h("section", { class: `fold ${cls}`.trim() }, button, inside);

  function apply(moved) {
    el.dataset.open = String(isOpen);
    button.setAttribute("aria-expanded", String(isOpen));
    mark.textContent = isOpen ? "▾" : "▸";
    if (isOpen && !filled) {
      filled = true;
      body(inside);
      finish(inside);
    }
    inside.hidden = !isOpen;
    if (moved && isOpen) {
      inside.classList.remove("opening");
      void inside.offsetWidth;
      inside.classList.add("opening");
    }
  }

  function toggle() {
    isOpen = !isOpen;
    state.set("open", { ...state.get("open", {}), [key]: isOpen });
    apply(true);
  }

  apply(false);
  return el;
}

// ---------- look ----------

const light = window.matchMedia("(prefers-color-scheme: light)");

// "auto" follows the system: the first theme of the system's scheme.
export function themeName() {
  const list = app.manifest.themes;
  if (list.some((theme) => theme.name === app.user.theme)) return app.user.theme;
  const want = light.matches ? "light" : "dark";
  return (list.find((theme) => theme.scheme === want) ?? list[0])?.name ?? "";
}

function applyUser() {
  const root = document.documentElement;
  root.dataset.motion = app.user.motion ? "on" : "off";
  root.lang = app.user.language || "zh";
  const theme = themeName();
  const link = document.getElementById("theme");
  const href = theme ? `/themes/${theme}.css` : "";
  if (link && link.getAttribute("href") !== href) link.setAttribute("href", href);
}

light.addEventListener?.("change", applyUser);

// ---------- page ----------
//
// A wiki-like page: a sidebar with the projects, a tree of contents and the
// settings; the record on the right, fully open. The tree comes from the
// panels: a panel can give `toc(record)` -> [{ id, title, mark?, note?, children? }],
// and it puts `id={anchor(panel.id, entry.id)}` on the element of each entry.
// mark: "done" | "doing" | "todo". A panel with `slot: "settings"` is shown
// in the settings window of the gear, not in the record.

const ANCHOR_UNSAFE = /[^a-zA-Z0-9_-]/g;

export function anchor(panelId, entryId) {
  const clean = (part) => String(part).replace(ANCHOR_UNSAFE, "_");
  return entryId === undefined ? `s-${clean(panelId)}` : `s-${clean(panelId)}-${clean(entryId)}`;
}

// Agent notes: details for the agents. Hidden unless the user turns them on.
export function notes(text) {
  if (!text || !app.user.notes) return null;
  return h("aside", { class: "notes", "data-scope": "" }, h("div", { class: "notes-label" }, t("core.notes", "agent 附注")), md(text));
}

const MARKS = { done: "●", doing: "◐", todo: "○" };

let settingsOpen = false;
let drawerOpen = false;

function mainPanels() {
  return registry.list("panel").filter((panel) => (panel.slot ?? "main") === "main");
}

function shown(panel) {
  try {
    return !panel.when || panel.when(app.task);
  } catch {
    return false;
  }
}

function tocEntries(panel) {
  try {
    return panel.toc ? panel.toc(app.task) ?? [] : [];
  } catch {
    return [];
  }
}

function goTo(id) {
  const target = document.getElementById(id);
  if (!target) return;
  history.replaceState(null, "", `${location.search}#${id}`);
  target.scrollIntoView({ behavior: app.user.motion ? "smooth" : "auto", block: "start" });
  drawerOpen = false;
  document.body.classList.remove("drawer-open");
}

function tocItem(panel, entry, depth) {
  const id = anchor(panel.id, entry.id);
  const kids = entry.children ?? [];
  const closed = state.get("toc", {})[id] === false;
  const toggle =
    kids.length > 0 &&
    h(
      "button",
      {
        type: "button",
        class: "toc-toggle",
        "aria-label": t("core.toggle", "展开或收起"),
        onclick: () => {
          state.set("toc", { ...state.get("toc", {}), [id]: closed });
          renderSidebar();
        },
      },
      closed ? "▸" : "▾",
    );
  return h(
    "li",
    { class: `toc-item depth-${depth}` },
    h(
      "div",
      { class: "toc-row" },
      toggle || h("span", { class: "toc-toggle" }),
      h(
        "a",
        { href: `#${id}`, "data-target": id, onclick: (event) => (event.preventDefault(), goTo(id)) },
        entry.mark && h("span", { class: `toc-mark ${entry.mark}`, title: entry.mark }, MARKS[entry.mark] ?? ""),
        h("span", { class: "toc-title" }, rich(entry.title)),
        entry.note && h("span", { class: "toc-note" }, rich(entry.note)),
      ),
    ),
    kids.length > 0 && !closed && h("ul", { class: "toc-list" }, kids.map((kid) => tocItem(panel, kid, depth + 1))),
  );
}

function tree() {
  if (!app.task) return null;
  const items = [];
  for (const panel of mainPanels()) {
    if (!shown(panel)) continue;
    const entries = tocEntries(panel);
    const id = anchor(panel.id);
    const closed = state.get("toc", {})[id] === false;
    let summary = "";
    try {
      summary = panel.tocNote ? panel.tocNote(app.task) : "";
    } catch {
      summary = "";
    }
    items.push(
      h(
        "li",
        { class: "toc-item depth-0" },
        h(
          "div",
          { class: "toc-row" },
          entries.length
            ? h(
                "button",
                {
                  type: "button",
                  class: "toc-toggle",
                  "aria-label": t("core.toggle", "展开或收起"),
                  onclick: () => {
                    state.set("toc", { ...state.get("toc", {}), [id]: closed });
                    renderSidebar();
                  },
                },
                closed ? "▸" : "▾",
              )
            : h("span", { class: "toc-toggle" }),
          h(
            "a",
            { href: `#${id}`, "data-target": id, onclick: (event) => (event.preventDefault(), goTo(id)) },
            h("span", { class: "toc-title" }, panel.title ? panel.title(app.task) : panel.id),
            summary && h("span", { class: "toc-note" }, rich(summary)),
          ),
        ),
        entries.length > 0 && !closed && h("ul", { class: "toc-list" }, entries.map((entry) => tocItem(panel, entry, 1))),
      ),
    );
  }
  return h("nav", { class: "toc", "aria-label": t("core.contents", "目录") }, h("ul", { class: "toc-list" }, items));
}

function switcher() {
  const projects = app.manifest.projects;
  const tasks = project()?.tasks ?? [];
  const parts = [];
  if (projects.length > 1) {
    parts.push(
      h(
        "select",
        {
          class: "switch",
          "aria-label": t("core.project", "项目"),
          onchange: (event) => choose(event.target.value, null),
        },
        projects.map((p) => h("option", { value: p.id, selected: p.id === app.projectId }, p.name)),
      ),
    );
  } else if (projects.length === 1) {
    parts.push(h("div", { class: "switch-one" }, projects[0].name));
  }
  if (tasks.length > 1) {
    parts.push(
      h(
        "div",
        { class: "records" },
        tasks.map((task) =>
          h(
            "button",
            { type: "button", class: task.id === app.taskId ? "record on" : "record", onclick: () => choose(app.projectId, task.id) },
            task.title,
          ),
        ),
      ),
    );
  }
  return parts;
}

function settingsWindow() {
  if (!settingsOpen) return null;
  const box = h("div", { class: "settings-pop", role: "dialog", "aria-label": t("core.settings", "设置") });
  for (const panel of registry.list("panel").filter((p) => p.slot === "settings")) {
    try {
      panel.render(app.task, box);
    } catch (err) {
      box.append(h("p", { class: "hot" }, `${panel.id}: ${err}`));
    }
  }
  return box;
}

function sidebar() {
  return h(
    "aside",
    { class: "sidebar", id: "sidebar" },
    h("div", { class: "side-top" }, h("div", { class: "brand" }, "EZ-COGNITION"), switcher()),
    h("div", { class: "side-tree" }, tree()),
    h(
      "div",
      { class: "side-bottom" },
      settingsWindow(),
      h(
        "button",
        {
          type: "button",
          class: settingsOpen ? "gear on" : "gear",
          "aria-expanded": String(settingsOpen),
          onclick: () => {
            settingsOpen = !settingsOpen;
            renderSidebar();
          },
        },
        h("span", { class: "gear-icon" }, "⚙"),
        t("core.settings", "设置"),
      ),
      status(),
    ),
  );
}

function renderSidebar() {
  const old = document.getElementById("sidebar");
  if (!old) return;
  const scroll = old.querySelector(".side-tree")?.scrollTop ?? 0;
  const fresh = sidebar();
  old.replaceWith(fresh);
  const box = fresh.querySelector(".side-tree");
  if (box) box.scrollTop = scroll;
  spy();
}

function trouble() {
  const lines = [...app.failed, ...app.problems];
  if (!lines.length) return null;
  return h(
    "div",
    { class: "trouble" },
    h("div", { class: "hot" }, t("core.trouble", "(*) 记录有问题。把下面的内容交给你的 agent。")),
    h("ul", { class: "points dim" }, lines.map((line) => h("li", null, line))),
  );
}

function sections() {
  const out = [];
  for (const panel of mainPanels()) {
    if (!shown(panel)) continue;
    let summary = "";
    try {
      summary = panel.summary ? panel.summary(app.task) : "";
    } catch {
      summary = "";
    }
    const body = h("div", { class: "section-body" });
    try {
      panel.render(app.task, body);
    } catch (err) {
      body.append(h("p", { class: "hot" }, t("core.broken", "这个栏目显示不出来："), String(err)));
    }
    out.push(
      h(
        "section",
        { class: `section panel-${panel.id}`, id: anchor(panel.id), "data-toc": "" },
        h("h2", { class: "section-title" }, panel.title ? panel.title(app.task) : panel.id),
        summary && h("p", { class: "section-summary" }, rich(summary)),
        body,
      ),
    );
  }
  return out;
}

function content() {
  if (!app.manifest.projects.length) {
    return h(
      "main",
      { class: "content" },
      h("h1", null, t("core.noproject", "还没有项目")),
      h("p", null, t("core.noproject.how", "在一个项目里让你的 agent 运行 open，这个项目就会出现在这里。")),
    );
  }
  if (!project()?.tasks.length) {
    return h(
      "main",
      { class: "content" },
      h("h1", null, t("core.empty", "还没有记录")),
      h("p", null, t("core.empty.how", "让组长的 agent 按 agent-guide.md 写一份。写好后，这个页面会自己刷新。")),
    );
  }
  if (!app.task) return h("main", { class: "content" }, trouble());
  // The sources stay in the record for the agents. The page does not show them.
  return h(
    "main",
    { class: "content" },
    h("h1", null, rich(app.task.title)),
    h("div", { class: "goal", "data-scope": "" }, md(app.task.goal)),
    trouble(),
    sections(),
  );
}

function status() {
  if (!app.online) {
    return h("div", { class: "status hot" }, t("core.offline", "服务已停止。让你的 agent 运行 open，这个页面会自己恢复。"));
  }
  const time = app.updated ? app.updated.toLocaleTimeString(undefined, { hour12: false }) : "";
  return h("div", { class: "status dim" }, t("core.online", "已连接，记录变了会自己刷新"), time && ` · ${time}`);
}

function phoneBar() {
  return h(
    "header",
    { class: "phone-bar" },
    h(
      "button",
      {
        type: "button",
        class: "menu",
        "aria-label": t("core.menu", "目录"),
        onclick: () => {
          drawerOpen = !drawerOpen;
          document.body.classList.toggle("drawer-open", drawerOpen);
        },
      },
      "☰",
    ),
    h("span", { class: "phone-title" }, app.task ? rich(app.task.title) : "ez-cognition"),
  );
}

// The entry of the tree that the reader is at: the last anchor above the top
// quarter of the window.
let spying = false;

function spy() {
  const anchors = [...document.querySelectorAll(".content [data-toc]")];
  const line = window.innerHeight * 0.25;
  let current = null;
  for (const el of anchors) {
    if (el.getBoundingClientRect().top <= line) current = el.id;
    else break;
  }
  for (const link of document.querySelectorAll(".toc a")) {
    link.classList.toggle("here", link.dataset.target === current);
  }
}

function watchScroll() {
  if (spying) return;
  spying = true;
  let queued = false;
  window.addEventListener(
    "scroll",
    () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        spy();
      });
    },
    { passive: true },
  );
}

// ---------- reminder ----------
//
// When an agent runs `open` and the page is already open, the page changes
// to that project. A page cannot bring its window to the front, so, when the
// user is not looking at it, it reminds the user in the usual way: a mark in
// the title of the tab, and a system notification (a click on it shows the
// tab). The browser asks for the permission once, after the first click on
// the page.

let marked = false;
let followed = false; // this load followed a new `open`

function setTitle() {
  const name = project()?.name;
  const title = [app.task?.title, name, "ez-cognition"].filter(Boolean).join(" · ");
  document.title = marked ? `● ${title}` : title;
}

function looking() {
  return document.visibilityState === "visible" && document.hasFocus();
}

function remind() {
  if (looking()) return;
  marked = true;
  setTitle();
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    const note = new Notification(t("core.remind", "ez-cognition 页面已打开"), {
      body: [project()?.name, app.task?.title].filter(Boolean).join(" · "),
      tag: "ezc-open",
    });
    note.onclick = () => {
      window.focus();
      note.close();
    };
  } catch {
    // The title mark is enough.
  }
}

function unmark() {
  if (!marked) return;
  marked = false;
  setTitle();
}

document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && unmark());
window.addEventListener("focus", unmark);
document.addEventListener(
  "click",
  () => {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
  },
  { once: true },
);

let firstRender = true;

function render() {
  setTitle();
  const root = document.getElementById("app");
  const scroll = window.scrollY;
  const treeScroll = document.querySelector(".side-tree")?.scrollTop ?? 0;
  root.replaceChildren(phoneBar(), h("div", { class: "layout" }, sidebar(), content()));
  finish(root);
  const box = document.querySelector(".side-tree");
  if (box) box.scrollTop = treeScroll;
  if (firstRender && location.hash) {
    firstRender = false;
    document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ block: "start" });
  } else {
    firstRender = false;
    window.scrollTo(0, scroll);
  }
  watchScroll();
  spy();
}

// ---------- data ----------

async function getJSON(url) {
  const reply = await fetch(url, { cache: "no-store" });
  return reply.json();
}

const asked = () => new URLSearchParams(location.search);

function seeFocus(at) {
  followed = true;
  focusSeen = at;
  try {
    sessionStorage.setItem(FOCUS_KEY, String(at));
  } catch {
    // See above.
  }
}

// The project in the address wins when the tab opens. After that, the page
// follows each new `open`.
function pickProject() {
  const ids = app.manifest.projects.map((p) => p.id);
  const focus = app.manifest.focus;
  const fresh = focus && focus.at > focusSeen && ids.includes(focus.project);
  if (app.projectId === null && ids.includes(asked().get("project"))) {
    if (fresh) seeFocus(focus.at);
    return asked().get("project");
  }
  if (fresh) {
    seeFocus(focus.at);
    return focus.project;
  }
  if (ids.includes(app.projectId)) return app.projectId;
  return ids[0] ?? null;
}

function pickTask() {
  const ids = (project()?.tasks ?? []).map((task) => task.id);
  if (ids.includes(app.taskId)) return app.taskId;
  if (asked().get("project") === app.projectId && ids.includes(asked().get("task"))) return asked().get("task");
  if (ids.includes(app.view._last)) return app.view._last;
  return ids[0] ?? null;
}

async function loadState() {
  const query = app.projectId ? `?project=${encodeURIComponent(app.projectId)}` : "";
  const stored = await getJSON(`/api/state${query}`);
  app.user = { ...app.user, ...stored.user };
  app.view = stored.view ?? {};
}

function remember() {
  if (!app.projectId) return;
  const query = new URLSearchParams({ project: app.projectId });
  if (app.taskId) query.set("task", app.taskId);
  history.replaceState(null, "", `?${query}${location.hash}`);
}

// The version of ez-cognition that this page's code comes from. A newer
// server has newer page code: the page loads it again.
let codeVersion = null;

async function load() {
  app.manifest = await getJSON("/api/manifest");
  codeVersion ??= app.manifest.version;
  if (app.manifest.version !== codeVersion) {
    await flush();
    location.reload();
    return;
  }
  const before = app.projectId;
  app.projectId = pickProject();
  if (app.projectId !== before) {
    await flush();
    app.taskId = null;
    await loadState();
  }
  app.taskId = pickTask();
  app.task = null;
  app.problems = [];
  if (app.taskId) {
    const query = new URLSearchParams({ project: app.projectId, id: app.taskId });
    const reply = await getJSON(`/api/task?${query}`);
    if (reply.ok) {
      app.task = reply.task;
      app.problems = reply.problems ?? [];
    } else {
      app.problems = [reply.error ?? "?"];
    }
  }
  app.updated = new Date();
  remember();
  applyUser();
  render();
  if (followed) {
    followed = false;
    remind();
  }
}

async function choose(projectId, taskId) {
  history.replaceState(null, "", location.search);
  window.scrollTo(0, 0);
  if (projectId !== app.projectId) {
    await flush();
    app.projectId = projectId;
    await loadState();
  }
  app.taskId = taskId;
  app.taskId = pickTask();
  app.view._last = app.taskId;
  save({ view: app.view });
  await load();
}

function listen() {
  const events = new EventSource("/api/events");
  events.onopen = () => {
    const back = !app.online;
    app.online = true;
    if (back) load().catch(() => render());
  };
  events.addEventListener("change", () => load().catch(() => {}));
  events.onerror = () => {
    if (app.online) {
      app.online = false;
      render();
    }
  };
}

async function boot() {
  app.manifest = await getJSON("/api/manifest");
  await loadState();
  if (app.user.language !== "zh" && app.manifest.locales.includes(app.user.language)) {
    locale = await getJSON(`/locales/${app.user.language}.json`).catch(() => ({}));
  }
  applyUser();
  for (const module of app.manifest.modules) {
    if (module.css) {
      document.head.append(h("link", { rel: "stylesheet", href: `/modules/${module.name}/module.css` }));
    }
    try {
      await import(`/modules/${module.name}/module.js`);
    } catch (err) {
      app.failed.push(`modules/${module.name}: ${err}`);
    }
  }
  app.online = true;
  await load();
  listen();
}

boot().catch((err) => {
  document.getElementById("app").replaceChildren(h("p", { class: "hot" }, String(err)));
});

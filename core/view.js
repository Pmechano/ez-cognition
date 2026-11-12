// The file viewer: one file or folder of a project, read-only.
//
//   /core/view.html?project=<id>&path=<path>[#L20-L40]
//
// Code and other text: with line numbers; "#L20-L40" marks those lines.
// CSV and TSV: a table. Markdown: rendered. A folder: its list. A PDF or an
// image: the browser shows the file itself. The server gives only files
// that are inside the project and not hidden or personal.

import { markdown } from "/core/md.js";

const MAX_LINES = 20000;
const MAX_ROWS = 2000;
const LOCAL = /^(?![/.])(?!.*(^|\/)\.)(?!.*\\)[^:*?"<>|]+$/;
const SHOWN = /\.(pdf|png|jpe?g|gif|webp|svg)$/i;

const asked = new URLSearchParams(location.search);
const project = asked.get("project") ?? "";
const path = asked.get("path") ?? "";
const view = document.getElementById("view");

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

const raw = (p) => `/raw/${encodeURIComponent(project)}/${p.split("/").filter(Boolean).map(encodeURIComponent).join("/")}`;

function viewURL(p, hash = "") {
  if (!p.endsWith("/") && SHOWN.test(p)) return raw(p) + hash;
  return `/core/view.html?${new URLSearchParams({ project, path: p })}${hash}`;
}

// A link in a Markdown file: relative to the folder of the file.
function resolve(href) {
  const at = href.indexOf("#");
  const target = at < 0 ? href : href.slice(0, at);
  const hash = at < 0 ? "" : href.slice(at);
  const parts = path.split("/").slice(0, -1);
  for (const part of target.split("/")) {
    if (part === "..") parts.pop();
    else if (part && part !== ".") parts.push(part);
  }
  const joined = parts.join("/") + (target.endsWith("/") ? "/" : "");
  return joined && LOCAL.test(joined) ? viewURL(joined, hash) : null;
}

async function json(url) {
  const reply = await fetch(url, { cache: "no-store" });
  return reply.json();
}

// The look of the main page: the user's theme, or the one of the system.
async function look() {
  try {
    const [manifest, state] = await Promise.all([json("/api/manifest"), json(`/api/state?project=${encodeURIComponent(project)}`)]);
    const list = manifest.themes ?? [];
    const want = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    const theme = list.some((x) => x.name === state.user?.theme)
      ? state.user.theme
      : (list.find((x) => x.scheme === want) ?? list[0])?.name;
    if (theme) document.getElementById("theme").setAttribute("href", `/themes/${theme}.css`);
    return manifest.projects?.find((p) => p.id === project)?.name ?? project;
  } catch {
    return project;
  }
}

function head(name) {
  const parts = path.split("/").filter(Boolean);
  const crumbs = [el("a", { href: viewURL("") }, name)];
  parts.forEach((part, index) => {
    const last = index === parts.length - 1;
    const here = parts.slice(0, index + 1).join("/") + (last && !path.endsWith("/") ? "" : "/");
    crumbs.push(el("span", { class: "dim" }, " / "), last ? el("strong", null, part) : el("a", { href: viewURL(here) }, part));
  });
  return el("header", { class: "viewer-head" }, el("div", { class: "viewer-path" }, crumbs));
}

function say(text, cls = "dim") {
  view.append(el("p", { class: cls }, text));
}

async function folder(p) {
  const reply = await json(`/api/dir?${new URLSearchParams({ project, path: p })}`);
  if (!reply.ok) return false;
  const base = p && !p.endsWith("/") ? `${p}/` : p;
  const rows = reply.entries.map((entry) => {
    const target = base + entry.name + (entry.dir ? "/" : "");
    return el(
      "li",
      null,
      el("a", { href: viewURL(target) }, entry.dir ? `${entry.name}/` : entry.name),
      entry.size !== null && el("span", { class: "dim" }, `  ${size(entry.size)}`),
    );
  });
  view.append(rows.length ? el("ul", { class: "viewer-list" }, rows) : el("p", { class: "dim" }, "这个文件夹是空的。"));
  if (reply.more) say("只列出了前 500 项。");
  return true;
}

function size(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// "#L20-L40" or "#L20" -> [20, 40]
function wanted() {
  const m = /^#L(\d+)(?:-L?(\d+))?$/.exec(location.hash);
  if (!m) return null;
  const from = Number(m[1]);
  return [from, Math.max(from, Number(m[2] ?? m[1]))];
}

function code(text) {
  const lines = text.replace(/\r\n?/g, "\n").replace(/\n$/, "").split("\n");
  const shown = lines.slice(0, MAX_LINES);
  const range = wanted();
  const rows = shown.map((line, index) => {
    const n = index + 1;
    const on = range && n >= range[0] && n <= range[1];
    return el(
      "tr",
      { id: `L${n}`, class: on ? "on" : null },
      el("td", { class: "ln" }, el("a", { href: `#L${n}` }, String(n))),
      el("td", { class: "src" }, line || " "),
    );
  });
  view.append(el("div", { class: "viewer-code" }, el("table", null, el("tbody", null, rows))));
  if (lines.length > MAX_LINES) say(`只显示了前 ${MAX_LINES} 行，共 ${lines.length} 行。`);
  if (range) document.getElementById(`L${range[0]}`)?.scrollIntoView({ block: "center" });
}

// A small CSV reader: quotes, quoted separators and quoted line breaks.
function rowsOf(text, sep) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"' && field === "") quoted = true;
    else if (c === sep) {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      if (rows.length > MAX_ROWS) break;
    } else field += c;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function table(text, sep) {
  const rows = rowsOf(text, sep);
  if (!rows.length) return say("这个文件是空的。");
  const [first, ...rest] = rows;
  const body = rest.slice(0, MAX_ROWS);
  view.append(
    el(
      "div",
      { class: "table viewer-table" },
      el(
        "table",
        null,
        el("thead", null, el("tr", null, first.map((cell) => el("th", null, cell)))),
        el("tbody", null, body.map((row) => el("tr", null, first.map((_, n) => el("td", null, row[n] ?? ""))))),
      ),
    ),
  );
  if (rest.length > MAX_ROWS) say(`只显示了前 ${MAX_ROWS} 行。`);
}

async function file(p) {
  const reply = await fetch(raw(p), { cache: "no-store" });
  if (reply.status === 404) {
    if (await folder(p)) return;
    return say("本地没有这个文件。它可能还没有 push，或者你还没有 pull。", "hot");
  }
  if (!reply.ok) return say(`这个文件显示不出来（${reply.status}）。`, "hot");
  const kind = reply.headers.get("Content-Type") ?? "";
  if (!kind.startsWith("text/plain")) {
    location.replace(raw(p));
    return;
  }
  const text = await reply.text();
  if (text.includes("\u0000")) {
    view.append(el("p", { class: "dim" }, "这是二进制文件，浏览器不能显示。", " ", el("a", { href: raw(p), download: "" }, "下载")));
    return;
  }
  const ext = (/\.([a-z0-9]+)$/i.exec(p)?.[1] ?? "").toLowerCase();
  if (ext === "md" || ext === "markdown") {
    view.append(el("article", { class: "card viewer-md" }, markdown(text, { image: () => null, link: resolve })));
  } else if (ext === "csv" || ext === "tsv") table(text, ext === "tsv" ? "\t" : ",");
  else code(text);
}

async function main() {
  const name = await look();
  document.title = `${path || name} · ez-cognition`;
  view.append(head(name));
  if (!project || (path && !LOCAL.test(path))) return say("这个地址不对。", "hot");
  if (!path || path.endsWith("/")) {
    if (!(await folder(path))) say("本地没有这个文件夹。", "hot");
    return;
  }
  await file(path);
}

window.addEventListener("hashchange", () => {
  const range = wanted();
  for (const row of document.querySelectorAll(".viewer-code tr")) {
    const n = Number(row.id.slice(1));
    row.classList.toggle("on", Boolean(range) && n >= range[0] && n <= range[1]);
  }
});

main().catch((err) => say(String(err), "hot"));

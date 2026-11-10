// ez-cognition core.
//
// The core knows nothing about tasks. It gives the modules four things:
// a registry, a page shell with folding panels, the personal state, and a
// refresh when a record changes. Everything that the page shows comes
// from a module in /modules/. The core must still run with no module.
//
// One page shows all the projects on this computer. A project has one or
// more tasks; the page shows one task at a time.
//
// A module is a folder with a module.js that imports this file and registers
// what it adds:
//
//   registry.add("panel", { id, order, title(task), summary(task), render(task, el), when(task) })
//
// A module can define its own kind and let other modules add to it. The
// steps module does this with "step-part".

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

// Text from a record. `like this` becomes code. Nothing else is markup.
export function rich(text) {
  const out = document.createDocumentFragment();
  for (const part of String(text ?? "").split(/(`[^`]+`)/)) {
    if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) out.append(h("code", null, part.slice(1, -1)));
    else if (part) out.append(part);
  }
  return out;
}

export function points(list) {
  return h("ul", { class: "points" }, (list ?? []).map((line) => h("li", null, rich(line))));
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
  user: { name: "", theme: "auto", motion: true, language: "zh" },
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

export function saveUser(patch) {
  Object.assign(app.user, patch);
  save({ user: { ...app.user } });
  applyUser();
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
    mark.textContent = isOpen ? "[-]" : "[+]";
    if (isOpen && !filled) {
      filled = true;
      body(inside);
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

function tabs(cls, items, current, pick) {
  return h(
    "nav",
    { class: cls },
    items.map((item) =>
      h(
        "button",
        {
          type: "button",
          class: item.id === current ? "tab on" : "tab",
          "aria-current": item.id === current ? "page" : null,
          onclick: () => pick(item.id),
        },
        item.label,
      ),
    ),
  );
}

function top() {
  const projects = app.manifest.projects;
  const tasks = project()?.tasks ?? [];
  return [
    h(
      "header",
      { class: "top" },
      h("span", { class: "brand" }, "EZ-COGNITION"),
      projects.length === 1 && h("span", { class: "dim" }, "// ", projects[0].name),
      projects.length > 1 &&
        tabs("projects", projects.map((p) => ({ id: p.id, label: p.name })), app.projectId, (id) => choose(id, null)),
    ),
    tasks.length > 1 &&
      tabs("tasks", tasks.map((task) => ({ id: task.id, label: task.title })), app.taskId, (id) => choose(app.projectId, id)),
  ];
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

function panels() {
  const out = [];
  for (const panel of registry.list("panel")) {
    try {
      if (panel.when && !panel.when(app.task)) continue;
      const title = panel.title ? panel.title(app.task) : panel.id;
      const summary = panel.summary ? panel.summary(app.task) : "";
      out.push(
        fold({
          key: `panel:${panel.id}`,
          open: panel.open ?? true,
          cls: `panel panel-${panel.id}`,
          head: [
            h("span", { class: "panel-title" }, "// ", title),
            h("span", { class: "panel-summary" }, summary ? rich(summary) : ""),
          ],
          body(el) {
            try {
              panel.render(app.task, el);
            } catch (err) {
              el.append(h("p", { class: "hot" }, t("core.broken", "这个栏目显示不出来："), String(err)));
            }
          },
        }),
      );
    } catch (err) {
      out.push(h("p", { class: "hot" }, `${panel.id}: ${err}`));
    }
  }
  return out;
}

function body() {
  if (!app.manifest.projects.length) {
    return h(
      "main",
      null,
      h("h1", null, t("core.noproject", "还没有项目")),
      h("p", null, t("core.noproject.how", "在一个项目里让你的 agent 运行 open，这个项目就会出现在这里。")),
      panels(),
    );
  }
  if (!project()?.tasks.length) {
    return h(
      "main",
      null,
      h("h1", null, t("core.empty", "还没有记录")),
      h("p", null, t("core.empty.how", "让组长的 agent 按 agent-guide.md 写一份。写好后，这个页面会自己刷新。")),
      panels(),
    );
  }
  if (!app.task) return h("main", null, trouble());
  const sources = Array.isArray(app.task.sources) ? app.task.sources : [];
  return h(
    "main",
    null,
    h("h1", null, rich(app.task.title)),
    h("p", { class: "goal" }, rich(app.task.goal)),
    sources.length > 0 && h("p", { class: "from" }, t("core.sources", "来源："), sources.join("  ")),
    trouble(),
    panels(),
  );
}

function status() {
  if (!app.online) {
    return h("footer", { class: "status hot" }, t("core.offline", "(*) 服务已停止。让你的 agent 运行 open，这个页面会自己恢复。"));
  }
  const time = app.updated ? app.updated.toLocaleTimeString(undefined, { hour12: false }) : "";
  return h("footer", { class: "status dim" }, t("core.online", "已连接。记录变了，页面会自己刷新。"), time && ` ${t("core.updated", "上次读取")} ${time}`);
}

function render() {
  const name = project()?.name;
  document.title = [app.task?.title, name, "ez-cognition"].filter(Boolean).join(" · ");
  document.getElementById("app").replaceChildren(...[...top(), body(), status()].filter(Boolean));
}

// ---------- data ----------

async function getJSON(url) {
  const reply = await fetch(url, { cache: "no-store" });
  return reply.json();
}

const asked = () => new URLSearchParams(location.search);

function seeFocus(at) {
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
  history.replaceState(null, "", `?${query}`);
}

async function load() {
  app.manifest = await getJSON("/api/manifest");
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
}

async function choose(projectId, taskId) {
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

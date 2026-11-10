// ez-cognition core.
//
// The core knows nothing about tasks. It gives the modules four things:
// a registry, a page shell with folding panels, the personal state, and a
// refresh when a task record changes. Everything that the page shows comes
// from a module in /modules/. The core must still run with no module.
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

// Text from a task record. `like this` becomes code. Nothing else is markup.
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
  manifest: { project: "", tasks: [], modules: [], themes: [], locales: [] },
  user: { name: "", theme: "amber", motion: true, language: "zh" },
  view: {},
  taskId: null,
  task: null,
  problems: [],
  failed: [],
  online: false,
  updated: null,
};

export const user = () => ({ ...app.user });
export const manifest = () => app.manifest;

let pending = {};
let timer = null;

function save(patch) {
  Object.assign(pending, patch);
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const body = pending;
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
  }, 200);
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

// ---------- page ----------

function applyUser() {
  const root = document.documentElement;
  root.dataset.motion = app.user.motion ? "on" : "off";
  root.lang = app.user.language || "zh";
  const themes = app.manifest.themes;
  const theme = themes.includes(app.user.theme) ? app.user.theme : themes[0];
  const link = document.getElementById("theme");
  const href = theme ? `/themes/${theme}.css` : "";
  if (link && link.getAttribute("href") !== href) link.setAttribute("href", href);
}

function top() {
  const tasks = app.manifest.tasks;
  return h(
    "header",
    { class: "top" },
    h("span", { class: "brand" }, "EZ-COGNITION"),
    h("span", { class: "dim" }, "// ", app.manifest.project),
    tasks.length > 1 &&
      h(
        "nav",
        { class: "tasks" },
        tasks.map((task) =>
          h(
            "button",
            {
              type: "button",
              class: task.id === app.taskId ? "tab on" : "tab",
              "aria-current": task.id === app.taskId ? "page" : null,
              onclick: () => choose(task.id),
            },
            task.title,
          ),
        ),
      ),
  );
}

function trouble() {
  const lines = [...app.failed, ...app.problems];
  if (!lines.length) return null;
  return h(
    "div",
    { class: "trouble" },
    h("div", { class: "hot" }, t("core.trouble", "(*) 任务记录有问题。把下面的内容交给你的 agent。")),
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
  if (!app.manifest.tasks.length) {
    return h(
      "main",
      null,
      h("h1", null, t("core.empty", "还没有任务记录")),
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
  return h("footer", { class: "status dim" }, t("core.online", "已连接。任务记录变了，页面会自己刷新。"), time && ` ${t("core.updated", "上次读取")} ${time}`);
}

function render() {
  document.title = app.task?.title ? `${app.task.title} · ez-cognition` : "ez-cognition";
  document.getElementById("app").replaceChildren(top(), body(), status());
}

// ---------- data ----------

async function getJSON(url) {
  const reply = await fetch(url, { cache: "no-store" });
  return reply.json();
}

function pickTask() {
  const ids = app.manifest.tasks.map((task) => task.id);
  const asked = new URLSearchParams(location.search).get("task");
  if (ids.includes(asked)) return asked;
  if (ids.includes(app.view._last)) return app.view._last;
  return ids[0] ?? null;
}

async function load() {
  app.manifest = await getJSON("/api/manifest");
  app.taskId = pickTask();
  app.task = null;
  app.problems = [];
  if (app.taskId) {
    const reply = await getJSON(`/api/task?id=${encodeURIComponent(app.taskId)}`);
    if (reply.ok) {
      app.task = reply.task;
      app.problems = reply.problems ?? [];
    } else {
      app.problems = [reply.error ?? "?"];
    }
  }
  app.updated = new Date();
  applyUser();
  render();
}

function choose(id) {
  history.replaceState(null, "", `?task=${encodeURIComponent(id)}`);
  app.view._last = id;
  save({ view: app.view });
  load();
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
  const stored = await getJSON("/api/state");
  app.user = { ...app.user, ...stored.user };
  app.view = stored.view ?? {};
  if (app.user.language !== "zh" && app.manifest.locales.includes(app.user.language)) {
    locale = await getJSON(`/locales/${app.user.language}.json`).catch(() => ({}));
  }
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

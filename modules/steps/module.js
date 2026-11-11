// Panel: our solution, step by step. Each step is a section of the page and
// an entry of the tree of contents, with its state.
// Data: record.steps = [{ id, title, ask, rubric?, for?: [deliverable ids], notes?, from? }]
//   ask     what the step asks, from the course materials (Markdown)
//   rubric  what the top band of the rubric asks for this step (Markdown)
//   notes   details for the agents; hidden unless the user turns notes on
//
// This module shows only what the step asks. What the group does about a
// step comes from other modules. They add a "step-part":
//
//   registry.add("step-part", {
//     id, order,
//     title(),               // the name of the part
//     data(step, task),      // the data that the part shows; a change marks the step
//     summary(step, task),   // one line about the step, or null
//     badge(step, task),     // { text, kind, mark } for the step, or null; mark: done | doing | todo
//     render(step, task, el) // the part inside the step
//   })

import { registry, h, rich, md, sig, t, state, anchor, notes } from "/core/core.js";

// task title -> (step id -> signature) at the last render, to show what changed.
const before = new Map();

const parts = () => registry.list("step-part");

function signature(step, task) {
  return sig([step, parts().map((part) => (part.data ? part.data(step, task) : null))]);
}

function first(step, task, key) {
  for (const part of parts()) {
    const value = part[key] ? part[key](step, task) : null;
    if (value) return value;
  }
  return null;
}

function usedIn(step, task) {
  if (!step.for?.length) return null;
  const byId = new Map((task.submit?.deliverables ?? []).map((d) => [d.id, d.title]));
  return step.for.map((id) => byId.get(id) ?? id).join("、");
}

function section(step, number, task, changed) {
  const now = signature(step, task);
  const marked = state.get("seen", {})[step.id];
  const stale = marked !== undefined && marked !== now;
  const badge = first(step, task, "badge");
  const used = usedIn(step, task);

  const el = h("section", { class: changed ? "step flash" : "step", id: anchor("steps", step.id), "data-toc": "" });
  const ack = h(
    "button",
    {
      type: "button",
      class: marked === now ? "step-ack on" : "step-ack",
      onclick: () => {
        const seen = { ...state.get("seen", {}) };
        if (seen[step.id] === now) delete seen[step.id];
        else seen[step.id] = now;
        state.set("seen", seen);
        el.replaceWith(section(step, number, task, false));
      },
    },
    marked === now ? "✓ " : "",
    t("steps.ack", "我已认知"),
  );
  const ours = h("div", { class: "step-ours" });
  for (const part of parts()) {
    const box = h("div", { class: `part part-${part.id}` });
    try {
      part.render(step, task, box);
    } catch (err) {
      box.append(h("p", { class: "hot" }, `${part.id}: ${err}`));
    }
    ours.append(box);
  }
  el.append(
    h(
      "h3",
      { class: "step-head" },
      h("span", { class: "step-no" }, String(number)),
      h("span", { class: "step-title" }, rich(step.title)),
      badge && h("span", { class: `badge ${badge.kind ?? ""}` }, badge.text),
      stale && h("span", { class: "badge hot", title: t("steps.stale", "你上次标记之后，这一步有更新。") }, t("steps.changed", "有更新")),
    ),
    h(
      "div",
      { class: "step-ask", "data-scope": "" },
      h("div", { class: "label" }, t("steps.ask", "这一步要做的")),
      md(step.ask),
      step.rubric && h("div", { class: "label" }, t("steps.rubric", "拿高分要做到")),
      step.rubric && md(step.rubric),
      used && h("div", { class: "step-used dim" }, t("steps.for", "用在："), used),
      notes(step.notes),
    ),
    ours,
    h("div", { class: "step-foot" }, ack),
  );
  return el;
}

function doneCount(task) {
  return task.steps.filter((step) => first(step, task, "badge")?.mark === "done").length;
}

registry.add("panel", {
  id: "steps",
  order: 30,
  when: (task) => Array.isArray(task?.steps),
  title: () => t("steps.title", "我们的方案"),
  summary: (task) => {
    const count = t("steps.count", "{n} 步").replace("{n}", task.steps.length);
    const done = doneCount(task);
    return done ? `${count}，${t("steps.done", "已完成 {n} 步").replace("{n}", done)}` : count;
  },
  tocNote: (task) => `${doneCount(task)}/${task.steps.length}`,
  toc: (task) =>
    task.steps.map((step, index) => ({
      id: step.id,
      title: `${index + 1} ${step.title}`,
      mark: first(step, task, "badge")?.mark ?? "todo",
    })),
  render(task, el) {
    const old = before.get(task.title);
    const now = new Map();
    task.steps.forEach((step, index) => {
      const mine = signature(step, task);
      now.set(step.id, mine);
      el.append(section(step, index + 1, task, old !== undefined && old.get(step.id) !== mine));
    });
    before.set(task.title, now);
  },
});

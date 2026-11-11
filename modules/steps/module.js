// Panel: our solution, step by step. One row for each step.
// Data: record.steps = [{ id, title, ask, rubric?, for?: [deliverable ids], from? }]
//   ask     what the step asks, from the course materials (Markdown)
//   rubric  what the top band of the rubric asks for this step (Markdown)
//
// This module shows only what the step asks. What the group does about a
// step comes from other modules. They add a "step-part":
//
//   registry.add("step-part", {
//     id, order,
//     title(),               // the name of the part, for the head of the panel
//     data(step, task),      // the data that the part shows; a change marks the row
//     summary(step, task),   // one line for the closed row, or null
//     badge(step, task),     // { text, kind } for the closed row, or null
//     render(step, task, el) // the inside of the open row
//   })

import { registry, h, rich, md, sig, t, fold, state } from "/core/core.js";

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

function row(step, number, task, changed) {
  const now = signature(step, task);
  const marked = state.get("seen", {})[step.id];
  const stale = marked !== undefined && marked !== now;
  const line = first(step, task, "summary");
  const badge = first(step, task, "badge");

  const flag = stale
    ? h("span", { class: "hot", title: t("steps.stale.tip", "你标记之后，这一步有更新") }, "●")
    : marked !== undefined
      ? h("span", { class: "ok", title: t("steps.ack", "我已认知") }, "✓")
      : "";

  const el = fold({
    key: `step:${step.id}`,
    cls: changed ? "step flash" : "step",
    head: [
      h("span", { class: "step-title" }, h("span", { class: "step-no" }, `${number}`), rich(step.title)),
      h("span", { class: line ? "step-line" : "step-line dim" }, line ? rich(line) : t("steps.none", "还没有方案")),
      h("span", { class: "step-flag" }, badge && h("span", { class: `badge ${badge.kind ?? ""}` }, badge.text), flag),
    ],
    body(inside) {
      const used = usedIn(step, task);
      const ask = h(
        "div",
        { class: "step-ask", "data-scope": "" },
        h("div", { class: "label" }, t("steps.ask", "这一步要做的")),
        md(step.ask),
        step.rubric && h("div", { class: "label" }, t("steps.rubric", "拿高分要做到")),
        step.rubric && md(step.rubric),
        used && h("div", { class: "step-used dim" }, t("steps.for", "用在："), used),
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
            el.replaceWith(row(step, number, task, false));
          },
        },
        marked === now ? "✓ " : "",
        t("steps.ack", "我已认知"),
      );
      inside.append(
        ask,
        ours,
        h(
          "div",
          { class: "step-foot" },
          ack,
          stale && h("span", { class: "hot" }, t("steps.stale", "你上次标记之后，这一步有更新。")),
        ),
      );
    },
  });
  return el;
}

registry.add("panel", {
  id: "steps",
  order: 30,
  when: (task) => Array.isArray(task?.steps),
  title: () => t("steps.title", "我们的方案"),
  summary: (task) => {
    const count = t("steps.count", "{n} 步").replace("{n}", task.steps.length);
    const done = task.steps.filter((step) => first(step, task, "badge")?.kind === "ok").length;
    return done ? `${count}，${t("steps.done", "已完成 {n} 步").replace("{n}", done)}` : count;
  },
  render(task, el) {
    const old = before.get(task.title);
    const now = new Map();
    task.steps.forEach((step, index) => {
      const mine = signature(step, task);
      now.set(step.id, mine);
      el.append(row(step, index + 1, task, old !== undefined && old.get(step.id) !== mine));
    });
    before.set(task.title, now);
  },
});

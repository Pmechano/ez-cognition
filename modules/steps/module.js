// Panel: the task, step by step. One row for each step.
// Data: record.steps = [{ id, title, ask, detail?: [..], for?: [deliverable ids], from? }]
//
// This module shows only what the step asks. What the group does about a
// step comes from other modules. They add a "step-part":
//
//   registry.add("step-part", {
//     id, order,
//     title(),               // the name of the part, for the head of the panel
//     data(step, task),      // the data that the part shows; a change marks the row
//     summary(step, task),   // one line for the closed row, or null
//     render(step, task, el) // the inside of the open row
//   })

import { registry, h, rich, points, sig, t, fold, state } from "/core/core.js";

// The deliverables that use a step, by their titles in the project panel.
function usedIn(step, task) {
  if (!step.for?.length) return null;
  const byId = new Map((task.project?.deliverables ?? []).map((d) => [d.id, d.title]));
  return step.for.map((id) => byId.get(id) ?? id).join("、");
}

// task title -> (step id -> signature) at the last render, to show what changed.
const before = new Map();

const parts = () => registry.list("step-part");

function signature(step, task) {
  return sig([step, parts().map((part) => (part.data ? part.data(step, task) : null))]);
}

function summaryOf(step, task) {
  for (const part of parts()) {
    const line = part.summary ? part.summary(step, task) : null;
    if (line) return line;
  }
  return null;
}

function row(step, number, task, changed) {
  const now = signature(step, task);
  const marked = state.get("seen", {})[step.id];
  const stale = marked !== undefined && marked !== now;
  const line = summaryOf(step, task);

  const flag = stale
    ? h("span", { class: "hot", title: t("steps.stale.tip", "你标记之后，这一步有更新") }, "(*)")
    : marked !== undefined
      ? h("span", { class: "dim", title: t("steps.ack", "我已认知") }, "[x]")
      : "";

  const el = fold({
    key: `step:${step.id}`,
    cls: changed ? "step flash" : "step",
    head: [
      h("span", { class: "step-title" }, h("span", { class: "dim" }, `${number} `), rich(step.title)),
      h(
        "span",
        { class: line ? "step-line" : "step-line dim" },
        h("span", { class: "dim" }, "=> "),
        line ? rich(line) : t("steps.none", "还没有方案"),
      ),
      h("span", { class: "step-flag" }, flag),
    ],
    body(inside) {
      const ask = h(
        "div",
        { class: "step-ask" },
        h("div", { class: "label" }, "// ", t("steps.ask", "这一步要做的")),
        h("p", null, rich(step.ask)),
        step.detail?.length > 0 && points(step.detail),
        usedIn(step, task) && h("div", { class: "dim" }, t("steps.for", "用在："), usedIn(step, task)),
        step.from && h("div", { class: "from" }, t("core.sources", "来源："), step.from),
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
          class: "step-ack",
          onclick: () => {
            const seen = { ...state.get("seen", {}) };
            if (seen[step.id] === now) delete seen[step.id];
            else seen[step.id] = now;
            state.set("seen", seen);
            el.replaceWith(row(step, number, task, false));
          },
        },
        marked === now ? "[x] " : "[ ] ",
        t("steps.ack", "我已认知"),
      );
      inside.append(
        h("div", { class: "step-cols" }, ask, ours),
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
  title: () => t("steps.title", "步骤与我们的方案"),
  // The head of the panel is also the head of the two columns.
  summary: (task) => {
    const count = t("steps.count", "{n} 步").replace("{n}", task.steps.length);
    const names = parts().map((part) => (part.title ? part.title() : null)).filter(Boolean);
    return names.length ? `${count} => ${names.join(" / ")}` : count;
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

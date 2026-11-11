// Step part: how the group does each step, and how far it is.
// Data: record.answers = { "<step id>": {
//   answer,                 // one or two sentences; the closed row shows the first line (Markdown)
//   detail?,                // more: the reasons, the settings, what is not decided (Markdown)
//   image?: { src, alt },   // shown beside the text
//   state?,                 // "todo" | "doing" | "done"
//   notes?,                 // details for the agents; hidden unless the user turns notes on
//   directions?: [{ id, who, explores, found?, state? }]
// } }
//
// `answer` and `detail` are the framework: the shared answer that the leader
// drafts. `directions` are what members explore inside it, and who explores
// them. The page shows who does what, but it never counts or compares work.

import { registry, h, rich, card, t, user, notes } from "/core/core.js";

const of = (step, task) => task.answers?.[step.id] ?? null;

const STATES = {
  todo: { text: () => t("answers.todo", "未开始"), kind: "", mark: "todo" },
  doing: { text: () => t("answers.doing", "进行中"), kind: "warn", mark: "doing" },
  done: { text: () => t("answers.done", "已完成"), kind: "ok", mark: "done" },
};

function badge(value) {
  const known = STATES[value];
  return known ? h("span", { class: `badge ${known.kind}` }, known.text()) : null;
}

registry.add("step-part", {
  id: "answers",
  order: 10,
  title: () => t("answers.title", "我们的方案"),
  data: of,
  summary: (step, task) => of(step, task)?.answer?.split("\n")[0] ?? null,
  badge: (step, task) => {
    const known = STATES[of(step, task)?.state];
    return known ? { text: known.text(), kind: known.kind, mark: known.mark } : null;
  },
  render(step, task, el) {
    const mine = of(step, task);
    el.append(h("div", { class: "label" }, t("answers.title", "我们的方案")));
    if (!mine) {
      el.append(h("p", { class: "dim" }, t("answers.none", "还没有方案。组长起草框架后，它会出现在这里。")));
      return;
    }
    const text = mine.detail ? `${mine.answer}\n\n${mine.detail}` : mine.answer;
    el.append(card({ text, image: mine.image, notes: mine.notes }, "answer-card"));

    const directions = mine.directions ?? [];
    if (!directions.length) return;
    const me = user().name;
    el.append(
      h("div", { class: "label" }, t("answers.directions", "谁在探索什么")),
      h(
        "ul",
        { class: "directions", "data-scope": "" },
        directions.map((d) =>
          h(
            "li",
            { class: "direction" },
            h("div", { class: "direction-head" }, h("strong", { class: me && d.who === me ? "me" : null }, d.who), badge(d.state)),
            h("div", null, rich(d.explores)),
            d.found && h("div", { class: "direction-found" }, h("span", { class: "dim" }, t("answers.found", "发现："), " "), rich(d.found)),
          ),
        ),
      ),
    );
  },
});

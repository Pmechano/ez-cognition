// Panel: the task. What the work is about, for a member who reads only this
// page: a set of questions and their answers, and the words that need an
// explanation. The project panel says what to hand in; this panel says what
// the work actually does.
// Data: record.task = {
//   summary,
//   questions: [{ ask, answer, detail?: [..], from? }],
//   terms?: [{ term, means }]
// }

import { registry, h, rich, points, t } from "/core/core.js";

registry.add("panel", {
  id: "task",
  order: 20,
  when: (record) => Boolean(record?.task),
  title: () => t("task.title", "任务"),
  summary: (record) => record.task.summary,
  render(record, el) {
    const task = record.task;
    const parts = [
      ...task.questions.map((q) =>
        h(
          "div",
          { class: "task-q" },
          h("div", { class: "label" }, "// ", rich(q.ask)),
          h("p", null, rich(q.answer)),
          q.detail?.length > 0 && points(q.detail),
          q.from && h("div", { class: "from" }, t("core.sources", "来源："), q.from),
        ),
      ),
      task.terms?.length > 0 &&
        h(
          "div",
          { class: "task-q" },
          h("div", { class: "label" }, "// ", t("task.terms", "词语")),
          h(
            "dl",
            { class: "task-terms" },
            task.terms.map((term) => [h("dt", { class: "bright" }, rich(term.term)), h("dd", null, rich(term.means))]),
          ),
        ),
    ];
    el.append(...parts.filter(Boolean));
  },
});

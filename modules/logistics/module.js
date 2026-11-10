// Panel: what the course asks for around the work. When it is due, what to
// hand in, the form of the presentation, the grading, the rules.
// Data: task.logistics = { summary, items: [{ label, value, note?, from? }] }

import { registry, h, rich, t } from "/core/core.js";

registry.add("panel", {
  id: "logistics",
  order: 10,
  when: (task) => Boolean(task?.logistics),
  title: () => t("logistics.title", "任务要求"),
  summary: (task) => task.logistics.summary,
  render(task, el) {
    const rows = (task.logistics.items ?? []).map((item) =>
      h(
        "div",
        { class: "logi-row" },
        h("div", { class: "logi-label dim" }, rich(item.label)),
        h(
          "div",
          { class: "logi-value" },
          h("div", null, rich(item.value)),
          item.note && h("div", { class: "dim" }, rich(item.note)),
          item.from && h("div", { class: "from" }, t("core.sources", "来源："), item.from),
        ),
      ),
    );
    el.append(h("div", { class: "logi" }, rows));
  },
});

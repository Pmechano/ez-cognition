// Panel: the task. A study note of the course's own task description: one
// card for each part of the source, in the order of the source. A card has
// Markdown text and, where it helps, an image beside the text.
// Data: record.task = { summary, cards: [{ title, text, image?: { src, alt } }] }

import { registry, card, t } from "/core/core.js";

registry.add("panel", {
  id: "task",
  order: 10,
  when: (record) => Boolean(record?.task),
  title: () => t("task.title", "任务"),
  summary: (record) => record.task.summary,
  render(record, el) {
    el.append(...record.task.cards.map((c) => card(c)));
  },
});

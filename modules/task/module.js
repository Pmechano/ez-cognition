// Panel: the task. A faithful study note of the course's own task
// description: one card for each part of the source, in the order of the
// source. A card has Markdown text and, where it helps, an image beside it.
// Data: record.task = { summary, cards: [{ title, text, image?: { src, alt }, notes? }] }
//
// In the tree of contents, a card whose title starts with a section number
// ("5.1 ...") sits under the card with the parent number ("5 ..."), when
// that card exists.

import { registry, card, anchor, t } from "/core/core.js";

const NUMBER = /^\s*(\d+(?:\.\d+)*)[.\s]/;

const cardId = (index) => `c${index + 1}`;

function entries(record) {
  const cards = record.task.cards.map((c, index) => ({ id: cardId(index), title: c.title, number: NUMBER.exec(c.title)?.[1], children: [] }));
  const byNumber = new Map(cards.filter((c) => c.number).map((c) => [c.number, c]));
  const top = [];
  for (const c of cards) {
    const parent = c.number && c.number.includes(".") ? byNumber.get(c.number.split(".").slice(0, -1).join(".")) : null;
    (parent ? parent.children : top).push(c);
  }
  return top;
}

registry.add("panel", {
  id: "task",
  order: 10,
  when: (record) => Boolean(record?.task),
  title: () => t("task.title", "任务"),
  summary: (record) => record.task.summary,
  toc: entries,
  render(record, el) {
    el.append(...record.task.cards.map((c, index) => card(c, "", anchor("task", cardId(index)))));
  },
});

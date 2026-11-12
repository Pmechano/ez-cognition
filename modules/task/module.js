// Panel: the task. A faithful study note of the course's own task
// description: one card for each part of the source, in the order of the
// source. A card has Markdown text and, where it helps, an image in it.
// Data: record.task = { summary, cards: [{ title, text, link?, image?: { src, alt }, notes? }] }
//   link  the place in the source; the title shows it as "原文"
//
// In the tree of contents, a card whose title starts with a section number
// ("5.1 ...") sits under the card with the parent number ("5 ..."), when
// that card exists.
//
// Other modules can put cards before the cards of the record:
//
//   registry.add("task-card", {
//     id, order,
//     title(record),     // the title, or null: then the card is not shown
//     render(record, id) // the card element; it carries id={id} and data-toc
//   })

import { registry, card, anchor, t } from "/core/core.js";

const NUMBER = /^\s*(\d+(?:\.\d+)*)[.\s]/;

const cardId = (index) => `c${index + 1}`;

const extraId = (extra) => `x-${extra.id}`;

function extras(record) {
  return registry.list("task-card").filter((extra) => extra.title(record));
}

function entries(record) {
  const titles = [
    ...extras(record).map((extra) => ({ id: extraId(extra), title: extra.title(record) })),
    ...record.task.cards.map((c, index) => ({ id: cardId(index), title: c.title })),
  ];
  const cards = titles.map((c) => ({ ...c, number: NUMBER.exec(c.title)?.[1], children: [] }));
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
    for (const extra of extras(record)) el.append(extra.render(record, anchor("task", extraId(extra))));
    el.append(...record.task.cards.map((c, index) => card(c, "", anchor("task", cardId(index)))));
  },
});

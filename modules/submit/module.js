// Panel: the submit requirements. It is the last panel: a member first needs
// only the deadlines and what to hand in, so each deliverable is one row.
// Data: record.submit = {
//   summary,
//   deliverables: [{ id, title, what, due?, done?, from? }],
//   items?: [{ label, value, from? }]       // grading and rules, short
// }

import { registry, h, rich, t } from "/core/core.js";

function row(item) {
  return h(
    "tr",
    { class: item.done ? "done" : null },
    h("td", { class: "sub-due" }, item.due ? rich(item.due) : h("span", { class: "dim" }, "—")),
    h(
      "td",
      { class: "sub-what" },
      h("strong", null, rich(item.title)),
      h("div", null, rich(item.what)),
    ),
    h(
      "td",
      { class: "sub-state" },
      item.done ? h("span", { class: "badge ok" }, t("submit.done", "已交")) : h("span", { class: "badge" }, t("submit.todo", "未交")),
    ),
  );
}

registry.add("panel", {
  id: "submit",
  order: 80,
  when: (record) => Boolean(record?.submit),
  title: () => t("submit.title", "提交要求"),
  summary: (record) => record.submit.summary,
  // The next deadline, beside the entry in the tree of contents.
  tocNote: (record) => {
    const next = (record.submit.deliverables ?? []).find((d) => !d.done && d.due);
    return next ? `${t("submit.next", "下一个")} ${next.due}` : "";
  },
  render(record, el) {
    const submit = record.submit;
    const list = submit.deliverables ?? [];
    const parts = [
      list.length > 0 &&
        h(
          "div",
          { class: "table", "data-scope": "" },
          h(
            "table",
            { class: "sub-table" },
            h(
              "thead",
              null,
              h("tr", null, h("th", null, t("submit.due", "截止")), h("th", null, t("submit.what", "要交什么")), h("th", null, t("submit.state", "状态"))),
            ),
            h("tbody", null, list.map((d) => row(d))),
          ),
        ),
      submit.items?.length > 0 &&
        h(
          "ul",
          { class: "sub-items", "data-scope": "" },
          submit.items.map((item) => h("li", null, h("strong", null, rich(item.label), "："), rich(item.value))),
        ),
    ];
    el.append(...parts.filter(Boolean));
  },
});

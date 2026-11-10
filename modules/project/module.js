// Panel: the project. What the course asks the group to hand in, how the
// deliverables follow each other, when they are due, and how they are graded.
// Data: record.project = {
//   summary, about?,
//   deliverables?: [{ id, title, what, due?, done?, uses?: [ids], note?, from? }],
//   items?: [{ label, value, note?, from? }]
// }

import { registry, h, rich, t } from "/core/core.js";

function deliverable(item, byId) {
  const uses = (item.uses ?? []).map((id) => byId.get(id)?.title ?? id);
  return h(
    "div",
    { class: "proj-row" },
    h(
      "div",
      { class: "proj-label" },
      h("div", { class: item.done ? "dim" : "bright" }, rich(item.title)),
      item.done
        ? h("div", { class: "dim" }, "[x] ", t("project.done", "已交"))
        : item.due && h("div", null, rich(item.due)),
    ),
    h(
      "div",
      { class: "proj-value" },
      h("div", null, rich(item.what)),
      uses.length > 0 && h("div", { class: "dim" }, t("project.uses", "接着做："), uses.join("、")),
      item.note && h("div", { class: "dim" }, rich(item.note)),
      item.from && h("div", { class: "from" }, t("core.sources", "来源："), item.from),
    ),
  );
}

function item(entry) {
  return h(
    "div",
    { class: "proj-row" },
    h("div", { class: "proj-label dim" }, rich(entry.label)),
    h(
      "div",
      { class: "proj-value" },
      h("div", null, rich(entry.value)),
      entry.note && h("div", { class: "dim" }, rich(entry.note)),
      entry.from && h("div", { class: "from" }, t("core.sources", "来源："), entry.from),
    ),
  );
}

registry.add("panel", {
  id: "project",
  order: 10,
  when: (record) => Boolean(record?.project),
  title: () => t("project.title", "项目"),
  summary: (record) => record.project.summary,
  render(record, el) {
    const project = record.project;
    const list = project.deliverables ?? [];
    const byId = new Map(list.map((d) => [d.id, d]));
    const parts = [
      project.about && h("p", { class: "proj-about" }, rich(project.about)),
      list.length > 0 &&
        h(
          "div",
          { class: "proj-part" },
          h("div", { class: "label" }, "// ", t("project.deliverables", "要交的东西（按先后）")),
          list.map((d) => deliverable(d, byId)),
        ),
      project.items?.length > 0 &&
        h(
          "div",
          { class: "proj-part" },
          h("div", { class: "label" }, "// ", t("project.items", "评分和规则")),
          project.items.map(item),
        ),
    ];
    el.append(...parts.filter(Boolean));
  },
});

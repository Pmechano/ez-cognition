// Files: what there is in the project, so that a member knows the files
// that the page talks about.
//
// Data: record.files = [{ path, what, step? }]
//   path  a file or a folder, from the project root, with "/"; a folder ends with "/"
//   what  one line: what it is (Markdown)
//   step  the id of the step that added it; without it, it was there at the start
//
// The task gets a first card, "0 开始时有的文件": the files and folders that
// have no step. Where the page names a file (its path, or its file name when
// only one file has that name), the name gets a note, like a term: what it
// is, where it comes from, and a link that opens it.

import { registry, h, rich, fileURL, anchor, t } from "/core/core.js";

const startFiles = (record) => (record.files ?? []).filter((f) => !f.step);

registry.add("task-card", {
  id: "files",
  order: 0,
  title: (record) => (startFiles(record).length ? t("files.start", "0 开始时有的文件") : null),
  render(record, id) {
    const rows = startFiles(record).map((f) => {
      const url = fileURL(f.path);
      const name = h("code", null, f.path);
      return h(
        "li",
        null,
        url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, name) : name,
        "：",
        rich(f.what),
      );
    });
    return h(
      "article",
      { class: "card files-card", "data-scope": "", id, "data-toc": "" },
      h(
        "div",
        { class: "card-text" },
        h("h3", { class: "card-title" }, t("files.start", "0 开始时有的文件")),
        h("ul", { class: "files-list" }, rows),
      ),
    );
  },
});

function fromText(file, steps) {
  if (!file.step) return t("files.atStart", "开始时就有。");
  const index = steps.findIndex((s) => s.id === file.step);
  if (index < 0) return "";
  const where = `第 ${index + 1} 步「${steps[index].title}」`;
  return t("files.fromStep", "来自{step}。").replace("{step}", `[${where}](#${anchor("steps", file.step)})`);
}

registry.add("term-source", {
  id: "files",
  terms(record) {
    const files = record.files ?? [];
    const steps = record.steps ?? [];
    const base = (path) => path.replace(/\/+$/, "").split("/").pop();
    const count = new Map();
    for (const f of files) if (!f.path.endsWith("/")) count.set(base(f.path), (count.get(base(f.path)) ?? 0) + 1);
    return files.map((f) => {
      const bare = f.path.replace(/\/+$/, "");
      const match = f.path.endsWith("/") ? [f.path, bare] : [bare];
      const name = base(f.path);
      if (!f.path.endsWith("/") && name !== bare && name.includes(".") && count.get(name) === 1) match.push(name);
      return {
        term: bare,
        match,
        head: `\`${f.path}\``,
        means: [f.what, fromText(f, steps)].filter(Boolean).join("\n\n"),
        href: fileURL(f.path),
        more: t("files.open", "打开"),
      };
    });
  },
});

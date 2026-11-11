// A small Markdown renderer for the text in a record.
//
// It builds DOM nodes and never sets innerHTML, so text from a record cannot
// become markup or script. It covers what a README needs: headings,
// paragraphs, bold, italic, code, links, images, ordered and unordered lists
// (nested), tables, quotes, rules, and math in $...$ and $$...$$.
//
//   markdown(text, { image(src) }) -> DocumentFragment
//   inline(text, { image(src) })   -> DocumentFragment
//
// `image(src)` turns a path from the record into a URL, or returns null when
// the image may not be shown. Math becomes <span class="math"> and
// <div class="math math-block"> with the TeX in `data-tex`; the core renders it.

function el(tag, attrs, kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value !== null && value !== undefined && value !== false) node.setAttribute(key, value === true ? "" : value);
  }
  for (const kid of kids ?? []) node.append(kid);
  return node;
}

// ---------- inline ----------

const INLINE = new RegExp(
  [
    String.raw`\\([\\` + "`" + String.raw`*_\[\]()$#|!~-])`, // 1: an escaped character
    "(`+)([^`]|[^`][\\s\\S]*?[^`])\\2(?!`)", // 2, 3: code
    String.raw`\$(?![\s$])((?:\\.|[^$\\\n])+?)(?<!\s)\$(?!\d)`, // 4: math
    String.raw`!\[([^\]]*)\]\(([^)\s]+)\)`, // 5, 6: image
    String.raw`\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)\s]+)\)`, // 7, 8: link
    String.raw`\*\*(?!\s)([\s\S]+?)(?<!\s)\*\*`, // 9: bold
    String.raw`(?<![\w*])\*(?![\s*])([\s\S]+?)(?<![\s*])\*(?![\w*])`, // 10: italic
  ].join("|"),
  "g",
);

const SAFE_LINK = /^(https?:\/\/|mailto:|#)/i;

export function inline(text, options = {}) {
  const out = document.createDocumentFragment();
  const source = String(text ?? "");
  // A new RegExp for each call: bold and link text call inline() again, and a
  // shared global RegExp would lose its place.
  const pattern = new RegExp(INLINE.source, "g");
  let last = 0;
  for (let m = pattern.exec(source); m; m = pattern.exec(source)) {
    if (m.index > last) out.append(source.slice(last, m.index));
    last = pattern.lastIndex;
    if (m[1] !== undefined) out.append(m[1]);
    else if (m[3] !== undefined) out.append(el("code", null, [m[3]]));
    else if (m[4] !== undefined) out.append(el("span", { class: "math", "data-tex": m[4] }, [m[4]]));
    else if (m[6] !== undefined) {
      const url = options.image ? options.image(m[6]) : null;
      out.append(url ? el("img", { src: url, alt: m[5], loading: "lazy" }) : m[5]);
    } else if (m[8] !== undefined) {
      const href = m[8];
      const kids = [inline(m[7], options)];
      out.append(SAFE_LINK.test(href) ? el("a", { href, target: "_blank", rel: "noopener noreferrer" }, kids) : kids[0]);
    } else if (m[9] !== undefined) out.append(el("strong", null, [inline(m[9], options)]));
    else if (m[10] !== undefined) out.append(el("em", null, [inline(m[10], options)]));
  }
  if (last < source.length) out.append(source.slice(last));
  return out;
}

// ---------- blocks ----------

const FENCE = /^\s*(```|~~~)/;
const HEADING = /^(#{1,4})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^\s*>\s?/;
const ITEM = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const FIGURE = /^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$/;
const MATH_FENCE = /^\s*\$\$/;

function startsBlock(line, next) {
  return (
    FENCE.test(line) || HEADING.test(line) || RULE.test(line) || QUOTE.test(line) || ITEM.test(line) ||
    MATH_FENCE.test(line) || FIGURE.test(line) || (line.trim().startsWith("|") && TABLE_SEP.test(next ?? ""))
  );
}

function cells(line) {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
}

function list(lines, options) {
  // Each line is an item or the continuation of the item above it. A deeper
  // indent starts a list inside the item above.
  const items = [];
  for (const line of lines) {
    const m = ITEM.exec(line);
    if (m) items.push({ indent: m[1].replace(/\t/g, "  ").length, ordered: /\d/.test(m[2]), start: parseInt(m[2], 10), text: m[3] });
    else if (items.length) items[items.length - 1].text += " " + line.trim();
  }
  function build(from, indent) {
    const first = items[from];
    const node = el(first.ordered ? "ol" : "ul", first.ordered && first.start !== 1 ? { start: first.start } : null);
    let i = from;
    while (i < items.length && items[i].indent >= indent) {
      const li = el("li", null, [inline(items[i].text, options)]);
      node.append(li);
      i += 1;
      if (i < items.length && items[i].indent > indent) {
        const [child, next] = build(i, items[i].indent);
        li.append(child);
        i = next;
      }
    }
    return [node, i];
  }
  const out = document.createDocumentFragment();
  let i = 0;
  while (i < items.length) {
    const [node, next] = build(i, items[i].indent);
    out.append(node);
    i = next;
  }
  return out;
}

export function figure(src, alt, options = {}) {
  const url = options.image ? options.image(src) : null;
  if (!url) return el("p", { class: "missing" }, [`[${alt || src}]`]);
  return el("figure", null, [el("img", { src: url, alt: alt ?? "", loading: "lazy" }), alt ? el("figcaption", null, [inline(alt, options)]) : ""]);
}

export function markdown(text, options = {}) {
  const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");
  const out = document.createDocumentFragment();
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (FENCE.test(line)) {
      const mark = FENCE.exec(line)[1];
      const body = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(mark)) body.push(lines[i++]);
      i += 1;
      out.append(el("pre", null, [el("code", null, [body.join("\n")])]));
      continue;
    }
    if (MATH_FENCE.test(line)) {
      let tex = line.trim().slice(2);
      if (tex.endsWith("$$")) {
        tex = tex.slice(0, -2);
        i += 1;
      } else {
        const body = [tex];
        i += 1;
        while (i < lines.length && !lines[i].includes("$$")) body.push(lines[i++]);
        if (i < lines.length) body.push(lines[i++].split("$$")[0]);
        tex = body.join("\n");
      }
      out.append(el("div", { class: "math math-block", "data-tex": tex.trim() }, [tex.trim()]));
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      out.append(el(`h${Math.min(heading[1].length + 2, 6)}`, null, [inline(heading[2], options)]));
      i += 1;
      continue;
    }
    if (RULE.test(line)) {
      out.append(el("hr"));
      i += 1;
      continue;
    }
    if (QUOTE.test(line)) {
      const body = [];
      while (i < lines.length && QUOTE.test(lines[i])) body.push(lines[i++].replace(QUOTE, ""));
      out.append(el("blockquote", null, [markdown(body.join("\n"), options)]));
      continue;
    }
    if (line.trim().startsWith("|") && TABLE_SEP.test(lines[i + 1] ?? "")) {
      const head = cells(line);
      const align = cells(lines[i + 1]).map((c) => (c.endsWith(":") ? (c.startsWith(":") ? "center" : "right") : null));
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      const cell = (tag, text, n) => el(tag, align[n] ? { style: `text-align:${align[n]}` } : null, [inline(text, options)]);
      out.append(
        el("div", { class: "table" }, [
          el("table", null, [
            el("thead", null, [el("tr", null, head.map((text, n) => cell("th", text, n)))]),
            el("tbody", null, rows.map((row) => el("tr", null, head.map((_, n) => cell("td", row[n] ?? "", n))))),
          ]),
        ]),
      );
      continue;
    }
    if (ITEM.test(line)) {
      const body = [];
      while (i < lines.length && lines[i].trim() && (ITEM.test(lines[i]) || /^\s+\S/.test(lines[i]) || !startsBlock(lines[i], lines[i + 1]))) {
        body.push(lines[i++]);
      }
      out.append(list(body, options));
      continue;
    }
    const pic = FIGURE.exec(line);
    if (pic) {
      out.append(figure(pic[2], pic[1], options));
      i += 1;
      continue;
    }
    const body = [];
    while (i < lines.length && lines[i].trim() && (body.length === 0 || !startsBlock(lines[i], lines[i + 1]))) {
      body.push(lines[i++].trim());
    }
    out.append(el("p", null, [inline(body.join("\n"), options)]));
  }
  return out;
}

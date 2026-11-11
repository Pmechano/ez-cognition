// Annotator: notes for the words that a member may not know.
// In each part of the page, the first use of a term gets a dotted line.
// Hover it, or tap it on a phone, and its note opens.
// Data: record.terms = [{ term, means }]

import { registry, h, rich } from "/core/core.js";

const SKIP = "code, pre, a, .term, .math, button, h1, .panel-summary";

function textNodes(root) {
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) out.push(node);
  return out;
}

function note(term) {
  return h(
    "span",
    { class: "term", tabindex: "0" },
    term.term,
    h("span", { class: "note", role: "tooltip" }, h("strong", null, term.term), " ", rich(term.means)),
  );
}

registry.add("annotator", {
  id: "terms",
  apply(root, record) {
    // Longer terms first, so "宏平均 F1" wins over "F1".
    const left = (record?.terms ?? []).filter((x) => x.term?.trim()).sort((a, b) => b.term.length - a.term.length);
    for (let node of textNodes(root)) {
      while (node && left.length) {
        const text = node.nodeValue;
        let best = null;
        for (const term of left) {
          const at = text.indexOf(term.term);
          if (at >= 0 && (best === null || at < best.at)) best = { at, term };
        }
        if (!best) break;
        const word = node.splitText(best.at);
        const rest = word.splitText(best.term.term.length);
        word.replaceWith(note(best.term));
        left.splice(left.indexOf(best.term), 1);
        node = rest;
      }
      if (!left.length) break;
    }
  },
});

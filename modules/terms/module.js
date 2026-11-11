// Notes for the words that a member may not know.
// In each part of the page, the first use of a term gets a dotted line.
// Pointing at it (or tapping it on a phone) opens a note. The note stays
// while the pointer moves onto it, so its link can be clicked: it closes
// 0.2 s after the pointer has left both the word and the note.
// Data: record.terms = [{ term, means, link? }]   means is Markdown; link is an https URL

import { registry, h, rich, md, t } from "/core/core.js";

const SKIP = "code, pre, a, .term, .math, button, h1, .section-summary, .toc";
const CLOSE_DELAY = 200;
const SAFE_LINK = /^https?:\/\//i;

const termOf = new WeakMap();

function textNodes(root) {
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) out.push(node);
  return out;
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
        const mark = h("span", { class: "term", tabindex: "0", role: "button", "aria-haspopup": "dialog" }, best.term.term);
        termOf.set(mark, best.term);
        word.replaceWith(mark);
        left.splice(left.indexOf(best.term), 1);
        node = rest;
      }
      if (!left.length) break;
    }
  },
});

// ---------- the one note window ----------

let box = null;
let owner = null;
let timer = null;

function window_() {
  if (box) return box;
  box = h("div", { class: "term-note", role: "dialog", hidden: true });
  box.addEventListener("pointerenter", () => clearTimeout(timer));
  box.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse") later();
  });
  document.body.append(box);
  return box;
}

function place(target) {
  const note = window_();
  const word = target.getBoundingClientRect();
  const gap = 6;
  const width = Math.min(note.offsetWidth, window.innerWidth - 16);
  let left = Math.min(Math.max(8, word.left), window.innerWidth - width - 8);
  let top = word.bottom + gap;
  if (top + note.offsetHeight > window.innerHeight - 8 && word.top - gap - note.offsetHeight > 8) {
    top = word.top - gap - note.offsetHeight;
  }
  note.style.left = `${left}px`;
  note.style.top = `${top}px`;
}

function show(target) {
  const term = termOf.get(target);
  if (!term) return;
  clearTimeout(timer);
  const note = window_();
  if (owner !== target) {
    owner?.classList.remove("open");
    owner = target;
    target.classList.add("open");
    const link = term.link && SAFE_LINK.test(term.link) ? term.link : null;
    note.replaceChildren(
      h("div", { class: "term-note-head" }, rich(term.term)),
      h("div", { class: "term-note-body" }, md(term.means)),
      link &&
        h(
          "a",
          { class: "term-note-link", href: link, target: "_blank", rel: "noopener noreferrer" },
          t("terms.more", "了解更多"),
          " ↗",
        ),
    );
  }
  note.hidden = false;
  place(target);
}

function hide() {
  clearTimeout(timer);
  if (box) box.hidden = true;
  owner?.classList.remove("open");
  owner = null;
}

function later() {
  clearTimeout(timer);
  timer = setTimeout(hide, CLOSE_DELAY);
}

const termAt = (event) => event.target instanceof Element ? event.target.closest(".term") : null;

document.addEventListener("pointerover", (event) => {
  const target = termAt(event);
  if (target && event.pointerType === "mouse") show(target);
});

document.addEventListener("pointerout", (event) => {
  const target = termAt(event);
  if (target && event.pointerType === "mouse" && !target.contains(event.relatedTarget)) later();
});

document.addEventListener("click", (event) => {
  const target = termAt(event);
  if (target) {
    if (owner === target && !box.hidden) hide();
    else show(target);
    return;
  }
  if (box && !box.contains(event.target)) hide();
});

document.addEventListener("focusin", (event) => {
  const target = termAt(event);
  if (target) show(target);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hide();
});

// The words move when the page scrolls; the note goes with its word.
window.addEventListener("scroll", () => owner && !box.hidden && place(owner), { passive: true });
window.addEventListener("resize", () => owner && !box.hidden && place(owner));

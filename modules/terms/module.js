// Notes for the words that a member may not know.
//
// In each part of the page, the first use of a term gets a dotted line.
// Pointing at it (or tapping it on a phone) opens a note. A note can name
// other terms; pointing at one of them opens a second note beside the
// first, and so on: the notes stay open together, as a chain.
//
// A note stays open while the pointer is on it, on its word, or on a deeper
// note. When the pointer leaves, the deeper notes close after 0.2 s. A term
// that is already open in the chain does not open again; its note lights up.
// Escape closes the top note; a click outside closes all (a tap closes the top).
//
// Data: record.terms = [{ term, means, link? }]   means is Markdown; link is an http(s) URL
//
// Other modules can add notes of their own (the files module does):
//
//   registry.add("term-source", { id, terms(record) -> [{
//     term,      // the name of the entry
//     match?,    // the texts that mark it; default [term]
//     head?,     // the head of the note (Markdown); default: term
//     means,     // the note (Markdown)
//     href?,     // a link at the bottom of the note
//     more?,     // the text of that link
//   }] })
//
// A text in `code` is marked too, when the whole text is one of the names.

import { registry, h, rich, md, t } from "/core/core.js";

const SKIP = "code, pre, a, .term, .math, button, h1, .section-summary, .toc, .term-note-head";
const NO_CODE = "pre, a, .term, .toc, .term-note-head";
const CLOSE_DELAY = 200;
const MAX_DEPTH = 4;
const SAFE_LINK = /^https?:\/\//i;

const termOf = new WeakMap();
let known = [];

// The text nodes and the `code` elements of `root`, in the order of the page.
function places(root) {
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        return node.tagName === "CODE" && !node.closest(NO_CODE) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
      return node.parentElement?.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    },
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) out.push(node);
  return out;
}

function markAs(el, entry) {
  el.classList.add("term");
  el.setAttribute("tabindex", "0");
  el.setAttribute("role", "button");
  el.setAttribute("aria-haspopup", "dialog");
  termOf.set(el, entry);
}

// Mark the first use of each entry in `root`.
function annotate(root, entries) {
  const left = new Set(entries);
  // Longer names first, so "宏平均 F1" wins over "F1".
  const names = entries
    .flatMap((entry) => (entry.match ?? [entry.term]).filter((name) => name?.trim()).map((name) => ({ name, entry })))
    .sort((a, b) => b.name.length - a.name.length);
  for (let node of places(root)) {
    if (!left.size) break;
    if (node.nodeType === Node.ELEMENT_NODE) {
      const text = node.textContent.trim();
      const hit = names.find((x) => left.has(x.entry) && x.name === text);
      if (hit) {
        markAs(node, hit.entry);
        left.delete(hit.entry);
      }
      continue;
    }
    while (node && left.size) {
      const text = node.nodeValue;
      let best = null;
      for (const x of names) {
        if (!left.has(x.entry)) continue;
        const at = text.indexOf(x.name);
        if (at >= 0 && (best === null || at < best.at)) best = { at, ...x };
      }
      if (!best) break;
      const word = node.splitText(best.at);
      const rest = word.splitText(best.name.length);
      const mark = h("span", null, best.name);
      markAs(mark, best.entry);
      word.replaceWith(mark);
      left.delete(best.entry);
      node = rest;
    }
  }
}

// The terms of the record, then the entries of other modules. The same
// objects for one record, so that the chain knows a term that is open.
const cache = new WeakMap();

function entriesOf(record) {
  if (record && cache.has(record)) return cache.get(record);
  const all = collect(record);
  if (record) cache.set(record, all);
  return all;
}

function collect(record) {
  const own = (record?.terms ?? []).map((x) => ({
    term: x.term,
    means: x.means,
    href: x.link && SAFE_LINK.test(x.link) ? x.link : null,
    more: t("terms.more", "了解更多"),
  }));
  const more = registry.list("term-source").flatMap((source) => {
    try {
      return source.terms(record ?? {}) ?? [];
    } catch {
      return [];
    }
  });
  return [...own, ...more].filter((x) => x.term?.trim());
}

registry.add("annotator", {
  id: "terms",
  apply(root, record) {
    known = entriesOf(record);
    annotate(root, known);
  },
});

// ---------- the chain of notes ----------

const chain = []; // [{ term, word, box }]; chain[0] is the note of a word in the page
let timer = null;

function boxOf(element) {
  return element instanceof Element ? element.closest(".term-note") : null;
}

function levelOf(word) {
  const box = boxOf(word);
  const at = chain.findIndex((entry) => entry.box === box);
  return at < 0 ? 0 : at + 1;
}

function build(term, level) {
  const body = h("div", { class: "term-note-body" }, md(term.means));
  const parts = [
    h("div", { class: "term-note-head" }, rich(term.head ?? term.term)),
    body,
    term.href &&
      h("a", { class: "term-note-link", href: term.href, target: "_blank", rel: "noopener noreferrer" }, term.more ?? t("terms.more", "了解更多"), " ↗"),
  ].filter(Boolean);
  const box = h("div", { class: "term-note", role: "dialog", "data-level": String(level) }, ...parts);
  if (level + 1 < MAX_DEPTH) {
    const open = new Set(chain.slice(0, level).map((entry) => entry.term));
    annotate(body, known.filter((x) => x !== term && !open.has(x)));
  }
  return box;
}

function place(entry, level) {
  const box = entry.box;
  const word = entry.word.getBoundingClientRect();
  const gap = 6;
  const width = Math.min(box.offsetWidth, window.innerWidth - 16);
  const height = box.offsetHeight;
  let left;
  let top;
  const parent = level > 0 ? chain[level - 1].box.getBoundingClientRect() : null;
  if (parent && parent.right + gap + width <= window.innerWidth - 8) {
    // Beside the note that names the word, so that the note stays readable.
    left = parent.right + gap;
    top = Math.min(Math.max(8, word.top - 12), window.innerHeight - height - 8);
  } else {
    left = Math.min(Math.max(8, word.left), window.innerWidth - width - 8);
    top = word.bottom + gap;
    if (top + height > window.innerHeight - 8 && word.top - gap - height > 8) top = word.top - gap - height;
  }
  box.style.left = `${left}px`;
  box.style.top = `${Math.max(8, top)}px`;
}

function placeAll() {
  chain.forEach((entry, level) => place(entry, level));
}

function trim(length) {
  clearTimeout(timer);
  while (chain.length > length) {
    const entry = chain.pop();
    entry.box.remove();
    entry.word.classList.remove("open");
  }
}

function open(word) {
  const term = termOf.get(word);
  if (!term) return;
  clearTimeout(timer);
  const level = levelOf(word);
  if (chain[level]?.word === word) return;
  const again = chain.findIndex((entry) => entry.term === term);
  if (again >= 0 && again < level) {
    const box = chain[again].box;
    box.classList.remove("ping");
    void box.offsetWidth;
    box.classList.add("ping");
    return;
  }
  trim(level);
  const box = build(term, level);
  box.style.zIndex = String(60 + level);
  document.body.append(box);
  word.classList.add("open");
  chain.push({ term, word, box });
  place(chain[level], level);
}

// The deepest note that the pointer is on: on the note itself, on its word,
// or on a note deeper in the chain.
function reached(target) {
  for (let level = chain.length - 1; level >= 0; level -= 1) {
    const { box, word } = chain[level];
    if (box.contains(target) || word.contains(target)) return level;
  }
  return -1;
}

function later(length) {
  clearTimeout(timer);
  timer = setTimeout(() => trim(length), CLOSE_DELAY);
}

const termAt = (target) => (target instanceof Element ? target.closest(".term") : null);

document.addEventListener("pointerover", (event) => {
  if (event.pointerType !== "mouse") return;
  const word = termAt(event.target);
  if (word) {
    open(word);
    return;
  }
  const level = reached(event.target);
  if (level === chain.length - 1) clearTimeout(timer);
  else later(level + 1);
});

document.addEventListener("pointerout", (event) => {
  if (event.pointerType !== "mouse" || event.relatedTarget) return;
  later(0); // the pointer left the window
});

document.addEventListener("click", (event) => {
  const word = termAt(event.target);
  if (word) {
    open(word);
    return;
  }
  const level = reached(event.target);
  if (level >= 0) {
    trim(level + 1);
    return;
  }
  // Outside all notes: a tap closes the top note, a click closes them all.
  trim(event.pointerType === "touch" ? chain.length - 1 : 0);
});

document.addEventListener("focusin", (event) => {
  const word = termAt(event.target);
  if (word) open(word);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && chain.length) trim(chain.length - 1);
});

// The words move when the page scrolls; the notes go with them.
window.addEventListener("scroll", () => chain.length && placeAll(), { passive: true });
window.addEventListener("resize", () => chain.length && placeAll());

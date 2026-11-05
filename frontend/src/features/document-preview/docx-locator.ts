import type { Schema } from "@/shared/api";

export type DocxLocator = Schema<"DocxLocator">;

/** Marks the nodes the preview adds (a value) or hides (dots), so they can be taken back. */
const VALUE = "data-preview-value";
const LEADER = "data-preview-leader";
const HIDDEN_TEXT = "data-text";
const EMPTY = "data-preview-empty";

/**
 * The paragraph a Word field's locator points at, in a docx-preview rendering (`inWrapper: false`):
 * the document body is the children of every page's `<article>`, its paragraphs and tables counted
 * apart, as python-docx counts them. Null when the rendering has no such paragraph.
 */
export function findParagraph(root: Element, locator: DocxLocator): HTMLElement | null {
  const body = [...root.querySelectorAll("section.docx > article")].flatMap((article) => [
    ...article.children,
  ]);
  if (locator.table === undefined || locator.table === null) {
    return asElement(body.filter((node) => node.tagName === "P")[locator.paragraph]);
  }
  const table = body.filter((node) => node.tagName === "TABLE")[locator.table];
  const row = table && rowsOf(table)[locator.row ?? 0];
  const cell = row && [...row.children].filter((node) => node.tagName === "TD")[locator.cell ?? 0];
  const paragraph =
    cell && [...cell.children].filter((node) => node.tagName === "P")[locator.paragraph];
  return asElement(paragraph);
}

/**
 * Show `value` in the rendered paragraph where the export writes it (blank: nothing, the original
 * text back). Idempotent: what an earlier call added for the same locator is taken back first.
 *
 * Returns the field's zone: the paragraph when the value fills it alone (an empty paragraph or
 * cell, the dots of a leader) or under a label (a new paragraph); else, when the value follows a
 * label on its line, the value itself, an empty placeholder (`data-preview-empty`) while blank, so
 * two fields sharing a line have a zone each.
 */
export function writePreviewValue(
  paragraph: HTMLElement,
  locator: DocxLocator,
  value: string | null,
): HTMLElement {
  const mark = markOf(locator);
  takeBack(paragraph, mark);
  const text = oneLine(value ?? "");
  const original = originalText(paragraph);
  if (!text) {
    if (locator.mode !== "in_paragraph" || !original.trim()) return paragraph;
    const placeholder = valueSpan("", mark);
    placeholder.setAttribute(EMPTY, "");
    insertAt(paragraph, locator.start ?? original.length, placeholder);
    return placeholder;
  }

  if (locator.mode === "new_paragraph") {
    const added = paragraph.cloneNode(false) as HTMLElement;
    added.removeAttribute("id");
    added.setAttribute(VALUE, mark);
    added.append(valueSpan(text, mark));
    paragraph.after(added);
    return added;
  }
  const start = locator.start ?? original.length;
  if (locator.mode === "replace_leader") {
    hideRange(paragraph, start, locator.end ?? start, mark);
    insertAt(paragraph, start, valueSpan(text, mark));
    return paragraph;
  }
  const before = original.slice(0, start);
  const written = before && !/\s$/.test(before) ? ` ${text}` : text;
  const span = valueSpan(written, mark);
  insertAt(paragraph, start, span);
  return original.trim() ? span : paragraph;
}

/** As the export writes it: on one line, Yes/No capitalised. */
function oneLine(value: string): string {
  const text = value.split(/\s+/).filter(Boolean).join(" ");
  const lower = text.toLowerCase();
  return lower === "yes" || lower === "no" ? lower[0].toUpperCase() + lower.slice(1) : text;
}

function markOf(locator: DocxLocator): string {
  return `${locator.mode}:${locator.start ?? "end"}`;
}

function asElement(node: Element | undefined): HTMLElement | null {
  return node instanceof HTMLElement ? node : null;
}

function rowsOf(table: Element): Element[] {
  return [...table.querySelectorAll(":scope > tr, :scope > tbody > tr, :scope > thead > tr")];
}

function valueSpan(text: string, mark: string): HTMLElement {
  const span = document.createElement("span");
  span.setAttribute(VALUE, mark);
  span.textContent = text;
  return span;
}

/** Remove what was added for this mark, and show again the dots it hid. */
function takeBack(paragraph: HTMLElement, mark: string) {
  const next = paragraph.nextElementSibling;
  if (next?.getAttribute(VALUE) === mark) next.remove();
  paragraph.querySelectorAll(`[${VALUE}="${mark}"]`).forEach((node) => node.remove());
  paragraph.querySelectorAll(`[${LEADER}="${mark}"]`).forEach((node) => {
    node.replaceWith(node.getAttribute(HIDDEN_TEXT) ?? "");
  });
}

/**
 * The paragraph's original text, piece by piece in order: its text nodes (added values left out)
 * and the dots hidden for another field (kept in an attribute, so they still count).
 */
function pieces(paragraph: HTMLElement): { node: Text | null; length: number }[] {
  const walker = document.createTreeWalker(
    paragraph,
    NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
  );
  const found: { node: Text | null; length: number }[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node instanceof Element) {
      if (node.hasAttribute(LEADER))
        found.push({ node: null, length: (node.getAttribute(HIDDEN_TEXT) ?? "").length });
      continue;
    }
    if (!node.parentElement?.closest(`[${VALUE}]`))
      found.push({ node: node as Text, length: (node as Text).data.length });
  }
  return found;
}

function originalText(paragraph: HTMLElement): string {
  return pieces(paragraph)
    .map(({ node, length }) => (node ? node.data : "\u2026".repeat(length)))
    .join("");
}

/** Insert `node` at character `offset` of the paragraph's original text. */
function insertAt(paragraph: HTMLElement, offset: number, node: Node) {
  let position = 0;
  for (const piece of pieces(paragraph)) {
    const end = position + piece.length;
    // Inside the label's text (or at its end): the value takes its formatting.
    if (piece.node && offset <= end && (offset > position || position === 0)) {
      piece.node.splitText(offset - position).before(node);
      return;
    }
    position = end;
  }
  paragraph.append(node);
}

/** Hide characters [start, end) of the paragraph's original text (the dots of a leader). */
function hideRange(paragraph: HTMLElement, start: number, end: number, mark: string) {
  let position = 0;
  for (const { node, length } of pieces(paragraph)) {
    const from = Math.max(start - position, 0);
    const to = Math.min(end - position, length);
    position += length;
    if (!node || from >= to) continue;
    const middle = from > 0 ? node.splitText(from) : node;
    middle.splitText(to - from);
    const hidden = document.createElement("span");
    hidden.setAttribute(LEADER, mark);
    hidden.setAttribute(HIDDEN_TEXT, middle.data);
    middle.replaceWith(hidden);
  }
}

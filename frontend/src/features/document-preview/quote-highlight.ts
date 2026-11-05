/**
 * Finding a quoted passage in a rendered document, to highlight it. Quotes are copied from the
 * passages the model read (verified by the back), but spacing and case can differ from the
 * rendering: both sides are compared normalized.
 */

/** Spacing and case ignored, typographic quotes and dashes made plain. */
export function normalizeText(text: string): string {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[‐-―]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/** The pieces of a quote: cut at its line breaks and ellipses (as the back verifies them). */
export function quotePieces(quote: string): string[] {
  return quote
    .split(/\n|…|\.\.\./)
    .map(normalizeText)
    .filter((piece) => piece.length > 0);
}

// Shorter bits of text (a digit, "AG") would be marked all over a page.
const MIN_ITEM_LENGTH = 4;

/**
 * Whether a text item of a PDF page (a run of text on one line) belongs to the quote: it is part
 * of a piece of the quote, or holds one.
 */
export function itemInQuote(item: string, quote: string): boolean {
  const text = normalizeText(item);
  if (text.length === 0) return false;
  return quotePieces(quote).some(
    (piece) => text.includes(piece) || (text.length >= MIN_ITEM_LENGTH && piece.includes(text)),
  );
}

/** Text to put in an HTML text layer: escaped, the part of the quote in a `<mark>`. */
export function markedItemHtml(item: string, quote: string): string {
  const escaped = item.replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
  return itemInQuote(item, quote) ? `<mark>${escaped}</mark>` : escaped;
}

/**
 * Wrap the first place where each piece of the quote is written in `root` in `<mark>` elements
 * (a piece may span several text nodes: one mark per node). Returns the first mark, or null when
 * the quote is not found.
 */
export function markQuote(root: HTMLElement, quote: string): HTMLElement | null {
  let first: HTMLElement | null = null;
  for (const piece of quotePieces(quote)) {
    const mark = markPiece(root, piece);
    first ??= mark;
  }
  return first;
}

/** Remove the marks `markQuote` added. */
export function unmarkQuotes(root: HTMLElement) {
  root.querySelectorAll(`mark[${MARK}]`).forEach((mark) => {
    mark.replaceWith(...mark.childNodes);
  });
  root.normalize();
}

const MARK = "data-quote-mark";

type Character = { node: Text; offset: number };

function markPiece(root: HTMLElement, piece: string): HTMLElement | null {
  // The text of the document, normalized character by character, each one mapped back to where
  // it is written.
  const characters: Character[] = [];
  let text = "";
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = (node as Text).data;
    for (let offset = 0; offset < value.length; offset++) {
      const character = normalizeText(value[offset]) || " ";
      // Runs of spaces count as one, as in the normalized piece.
      if (character === " " && (text.length === 0 || text.endsWith(" "))) continue;
      text += character;
      characters.push({ node: node as Text, offset });
    }
  }
  const start = text.indexOf(piece);
  if (start < 0) return null;
  const end = start + piece.length - 1;
  return wrap(characters[start], characters[end]);
}

/** Wrap the text from `from` to `to` (both included) in marks, one per text node. */
function wrap(from: Character, to: Character): HTMLElement | null {
  const nodes: Text[] = [];
  const walker = from.node.ownerDocument.createTreeWalker(
    from.node.ownerDocument.body,
    NodeFilter.SHOW_TEXT,
  );
  walker.currentNode = from.node;
  for (let node: Node | null = from.node; node; node = walker.nextNode()) {
    nodes.push(node as Text);
    if (node === to.node) break;
  }
  let first: HTMLElement | null = null;
  for (const node of nodes) {
    const start = node === from.node ? from.offset : 0;
    const end = node === to.node ? to.offset + 1 : node.data.length;
    if (end <= start) continue;
    const range = node.ownerDocument.createRange();
    range.setStart(node, start);
    range.setEnd(node, end);
    const mark = node.ownerDocument.createElement("mark");
    mark.setAttribute(MARK, "");
    range.surroundContents(mark);
    first ??= mark;
  }
  return first;
}

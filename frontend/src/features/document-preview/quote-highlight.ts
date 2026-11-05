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

/**
 * The pieces of a quote: cut at its line breaks and ellipses (as the back verifies them), and
 * between the cells of a table row (passages write them "cell | cell").
 */
export function quotePieces(quote: string): string[] {
  return quote
    .split(/\n|…|\.\.\.|\s\|\s/)
    .map(normalizeText)
    .filter((piece) => piece.length > 0);
}

/**
 * The text items of a PDF page (runs of text, in reading order) that hold the quote: each piece
 * is looked for in the page's text, items joined, and the items it overlaps are returned. Only
 * the first place of each piece: a word of the quote found elsewhere on the page is not marked.
 */
export function quoteItems(items: string[], quote: string): Set<number> {
  // The page's text, normalized, each character mapped to its item.
  let text = "";
  const itemOf: number[] = [];
  items.forEach((item, index) => {
    for (const character of ` ${item}`) {
      const normalized = normalizeText(character) || " ";
      if (normalized === " " && (text.length === 0 || text.endsWith(" "))) continue;
      text += normalized;
      itemOf.push(index);
    }
  });
  const found = new Set<number>();
  for (const [start, end] of findPieces(text, quotePieces(quote))) {
    for (let at = start; at <= end; at++) {
      // A space between two items belongs to neither.
      if (text[at] !== " ") found.add(itemOf[at]);
    }
  }
  return found;
}

/**
 * Where each piece is in `text` (first and last character): each one looked for after the
 * previous one, as they follow each other in the quote (else from the start). Pieces not found
 * are left out.
 */
function findPieces(text: string, pieces: string[]): [number, number][] {
  const ranges: [number, number][] = [];
  let from = 0;
  for (const piece of pieces) {
    let start = text.indexOf(piece, from);
    if (start < 0) start = text.indexOf(piece);
    if (start < 0) continue;
    ranges.push([start, start + piece.length - 1]);
    from = start + piece.length;
  }
  return ranges;
}

/** Text to put in an HTML text layer: escaped, in a `<mark>` when it is part of the quote. */
export function markedItemHtml(item: string, marked: boolean): string {
  const escaped = item.replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
  return marked ? `<mark>${escaped}</mark>` : escaped;
}

/**
 * Wrap the first place where each piece of the quote is written in `root` in `<mark>` elements
 * (a piece may span several text nodes: one mark per node). Returns the first mark, or null when
 * the quote is not found.
 */
export function markQuote(root: HTMLElement, quote: string): HTMLElement | null {
  const { text, characters } = readText(root);
  const ranges = findPieces(text, quotePieces(quote));
  // From the last piece to the first: wrapping one splits its text nodes, the places of the
  // pieces before it stay valid.
  let first: HTMLElement | null = null;
  for (const [start, end] of [...ranges].sort((a, b) => b[0] - a[0])) {
    first = wrap(characters[start], characters[end]) ?? first;
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

/** The text of `root`, normalized character by character, each one mapped to where it is. */
function readText(root: HTMLElement): { text: string; characters: Character[] } {
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
  return { text, characters };
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

/**
 * Page numbers of a docx-preview rendering. docx-preview does not compute Word fields: it shows the
 * result Word last saved ("Page 1" on every page). The PAGE and NUMPAGES results are marked in the
 * parsed document before rendering, then numbered once the pages are laid out (`paginate`).
 */

const PAGE = "page";
const PAGE_COUNT = "pages";
const FIELDS: [RegExp, string][] = [
  [/^\s*PAGE\b/i, PAGE],
  [/^\s*NUMPAGES\b/i, PAGE_COUNT],
];

/** A node of docx-preview's parsed tree (only what is read here). */
type ParsedNode = {
  type?: string;
  text?: string;
  charType?: string;
  children?: ParsedNode[];
};

/** Replace the saved result of each PAGE / NUMPAGES field by a mark, in every part. */
export function markPageFields(parsed: { parts?: { rootElement?: ParsedNode }[] }): void {
  for (const part of parsed.parts ?? []) {
    if (part.rootElement) markIn(part.rootElement, { field: null });
  }
}

type State = {
  field: { instruction: string; result: boolean; mark: string | null; written: boolean } | null;
};

function markIn(node: ParsedNode, state: State): void {
  if (node.type === "complexField") {
    if (node.charType === "begin") {
      state.field = { instruction: "", result: false, mark: null, written: false };
    } else if (node.charType === "separate" && state.field) {
      state.field.result = true;
      state.field.mark = FIELDS.find(([name]) => name.test(state.field!.instruction))?.[1] ?? null;
    } else if (node.charType === "end") {
      state.field = null;
    }
    return;
  }
  if (node.type === "instruction" && state.field && !state.field.result) {
    state.field.instruction += node.text ?? "";
    return;
  }
  if (node.type === "text" && state.field?.result && state.field.mark) {
    node.text = state.field.written ? "" : state.field.mark;
    state.field.written = true;
    return;
  }
  for (const child of node.children ?? []) markIn(child, state);
}

/** Write each page's number, and the page count, where the marks are. */
export function numberPages(root: HTMLElement): void {
  const pages = [...root.querySelectorAll("section.docx")];
  pages.forEach((page, index) => {
    const walker = document.createTreeWalker(page, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node as Text;
      if (!text.data.includes("")) continue;
      text.data = text.data
        .replaceAll(PAGE, String(index + 1))
        .replaceAll(PAGE_COUNT, String(pages.length));
    }
  });
}

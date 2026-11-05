/**
 * Pages of a docx-preview rendering, as on paper. docx-preview only breaks pages where the document
 * says so (page breaks, sections): its pages grow as long as their content. Here, what passes the
 * bottom of a page goes to a new page of the same size, a table breaking between two rows. Needs a
 * real layout (a browser): measured with `getBoundingClientRect`, unscaled.
 */

/** Marks the part of a table carried over to the next page (the export counts it as one table). */
export const CONTINUED = "data-continued";

/** Where an element is on screen, in px (injected by the tests, which have no layout). */
export type Measure = { top: (element: Element) => number; bottom: (element: Element) => number };

const browserMeasure: Measure = {
  top: (element) => element.getBoundingClientRect().top,
  bottom: (element) => element.getBoundingClientRect().bottom,
};

export function paginate(root: HTMLElement, measure: Measure = browserMeasure): void {
  const sections = [...root.querySelectorAll<HTMLElement>("section.docx")];
  for (let index = 0; index < sections.length; index++) {
    const next = splitPage(sections[index], measure);
    if (next) sections.splice(index + 1, 0, next);
  }
}

/** Move what does not fit in the page to a new page right after it (returned), if anything. */
function splitPage(section: HTMLElement, measure: Measure): HTMLElement | null {
  const article = section.querySelector<HTMLElement>(":scope > article");
  if (!article) return null;
  const limit = measure.top(section) + toPx(section.style.minHeight) - toPx(paddingBottom(section));
  const blocks = [...article.children];
  for (const [index, block] of blocks.entries()) {
    if (measure.bottom(block) <= limit) continue;
    const first = index === 0;
    const carried = block.tagName === "TABLE" ? splitTable(block, limit, first, measure) : null;
    // A block alone on its page and taller than it stays there (it cannot be cut).
    if (!carried && first) continue;
    const page = newPage(section);
    const pageArticle = page.querySelector("article")!;
    let node: Element | null = carried ?? block;
    while (node) {
      const following: Element | null =
        node === carried ? block.nextElementSibling : node.nextElementSibling;
      pageArticle.append(node);
      node = following;
    }
    section.after(page);
    return page;
  }
  return null;
}

/** The rows of `table` from the first that passes `limit`, in a copy of the table (or null). */
function splitTable(
  table: Element,
  limit: number,
  first: boolean,
  measure: Measure,
): Element | null {
  const rows = [...table.querySelectorAll(":scope > tr, :scope > tbody > tr")];
  // On top of its page, a table keeps at least its first row.
  const from = rows.findIndex((row, index) => (index > 0 || !first) && measure.bottom(row) > limit);
  if (from <= 0) return null;
  const carried = table.cloneNode(false) as Element;
  carried.setAttribute(CONTINUED, "");
  const columns = table.querySelector(":scope > colgroup");
  if (columns) carried.append(columns.cloneNode(true));
  carried.append(...rows.slice(from));
  return carried;
}

/** An empty page like `section`, with its footer (the first page's header is its own). */
function newPage(section: HTMLElement): HTMLElement {
  const page = section.cloneNode(false) as HTMLElement;
  page.removeAttribute("id");
  page.append(document.createElement("article"));
  const footer = section.querySelector(":scope > footer");
  if (footer) page.append(footer.cloneNode(true));
  return page;
}

function paddingBottom(section: HTMLElement): string {
  return section.style.paddingBottom || section.style.padding.split(" ")[2] || "0pt";
}

/** A CSS length in px (docx-preview writes pt). */
function toPx(length: string): number {
  const match = /^([\d.]+)(pt|px)$/.exec(length.trim());
  if (!match) return 0;
  return match[2] === "pt" ? (Number(match[1]) * 4) / 3 : Number(match[1]);
}

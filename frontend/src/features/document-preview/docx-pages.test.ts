import { findParagraph, type DocxLocator } from "./docx-locator";
import { paginate, type Measure } from "./docx-pages";

/**
 * A rendered document with a fake layout: each element declares its height (`data-h`, px) and is
 * stacked under the previous one in its page; a page is 400 px high with 40 px of bottom margin.
 */
function rendered(body: string): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML =
    `<section class="docx" style="min-height: 300pt; padding: 0pt 0pt 30pt;">` +
    `<article>${body}</article><footer>Page footer</footer></section>`;
  return root;
}

/** Elements stacked from the top of their page, a table's rows stacked inside it. */
const stacked: Measure = {
  top: (element) => {
    const section = element.closest("section");
    if (element === section) return 1000 * [...section!.parentElement!.children].indexOf(section!);
    const parent = element.parentElement!;
    const before = [...parent.children].slice(0, [...parent.children].indexOf(element));
    const start = parent.tagName === "ARTICLE" ? stacked.top(section!) : stacked.top(parent);
    return start + before.reduce((sum, node) => sum + height(node), 0);
  },
  bottom: (element) => stacked.top(element) + height(element),
};

function height(element: Element): number {
  if (element.tagName === "TABLE" || element.tagName === "TBODY") {
    return [...element.children].reduce((sum, row) => sum + height(row), 0);
  }
  return Number(element.getAttribute("data-h") ?? 0);
}

const pages = (root: HTMLElement) =>
  [...root.querySelectorAll("section.docx")].map((section) =>
    [...section.querySelector("article")!.children].map((node) => node.textContent),
  );

describe("paging a rendered Word document", () => {
  test("moves what passes the bottom of a page to the next page", () => {
    const root = rendered(
      `<p data-h="150">A</p><p data-h="150">B</p><p data-h="150">C</p><p data-h="150">D</p>`,
    );

    paginate(root, stacked);

    expect(pages(root)).toEqual([
      ["A", "B"],
      ["C", "D"],
    ]);
    // Each page keeps the footer
    expect(root.querySelectorAll("section.docx > footer")).toHaveLength(2);
  });

  test("breaks a table between two rows", () => {
    const root = rendered(
      `<p data-h="100">Intro</p><table><tr data-h="100"><td><p>R1</p></td></tr>` +
        `<tr data-h="100"><td><p>R2</p></td></tr><tr data-h="100"><td><p>R3</p></td></tr></table>`,
    );

    paginate(root, stacked);

    expect(pages(root)).toEqual([["Intro", "R1R2"], ["R3"]]);
  });

  test("keeps a block taller than a page where it is", () => {
    const root = rendered(`<p data-h="900">Long</p><p data-h="10">After</p>`);

    paginate(root, stacked);

    expect(pages(root)).toEqual([["Long"], ["After"]]);
  });

  test("finds a field in a table that runs over two pages", () => {
    const root = rendered(
      `<p data-h="100">Intro</p><table><tr data-h="100"><td><p>R1</p></td></tr>` +
        `<tr data-h="100"><td><p>R2</p></td></tr><tr data-h="100"><td><p>R3</p></td></tr></table>` +
        `<table><tr data-h="10"><td><p>Next table</p></td></tr></table>`,
    );
    const at = (table: number, row: number) =>
      ({ format: "docx", table, row, cell: 0, paragraph: 0, mode: "in_paragraph" }) as DocxLocator;

    paginate(root, stacked);

    expect(findParagraph(root, at(0, 2))?.textContent).toBe("R3");
    expect(findParagraph(root, at(1, 0))?.textContent).toBe("Next table");
  });
});

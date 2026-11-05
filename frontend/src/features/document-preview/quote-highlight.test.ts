import { describe, expect, it } from "vitest";
import {
  quoteItems,
  markedItemHtml,
  markQuote,
  quotePieces,
  unmarkQuotes,
} from "./quote-highlight";

function page(html: string) {
  const root = document.createElement("div");
  root.innerHTML = html;
  document.body.replaceChildren(root);
  return root;
}

const marked = (root: HTMLElement) =>
  [...root.querySelectorAll("mark")].map((mark) => mark.textContent).join("|");

describe("quotePieces", () => {
  it("cuts a quote at its line breaks and ellipses, normalized", () => {
    expect(quotePieces("Alpenlogic  AG … Zurich\nCHE-123")).toEqual([
      "alpenlogic ag",
      "zurich",
      "che-123",
    ]);
  });
});

describe("quoteItems (PDF text items)", () => {
  // A table row of the commercial register, then other rows naming Zurich again.
  const items = [
    "Registered office",
    "Zurich (ZH)",
    "Address",
    "Pfingstweidstrasse 31, 8005 Zurich",
    "Keller, Marc",
    "Zurich",
  ];

  it("marks the items the quote runs over, across items", () => {
    expect([...quoteItems(items, "Address Pfingstweidstrasse 31, 8005 Zurich")]).toEqual([2, 3]);
  });

  it("marks only where the quote is, not the same words elsewhere on the page", () => {
    expect([...quoteItems(items, "Zurich (ZH)")]).toEqual([1]);
  });

  it("marks each piece of a quote cut by an ellipsis, and nothing when it is not there", () => {
    expect([...quoteItems(items, "Registered office … Keller, Marc")]).toEqual([0, 4]);
    expect(quoteItems(items, "Bern").size).toBe(0);
  });

  it("escapes the text it puts in the text layer", () => {
    expect(markedItemHtml("<b>AG</b>", false)).toBe("&#60;b&#62;AG&#60;/b&#62;");
    expect(markedItemHtml("Alpenlogic AG", true)).toBe("<mark>Alpenlogic AG</mark>");
  });
});

describe("markQuote (rendered Word documents)", () => {
  it("marks the quote where it is written, across runs and spacing", () => {
    const root = page(
      "<p><span>Registered office: </span><span>Bahnhof</span><span>strasse 1,   8001</span> Zurich</p>",
    );
    const first = markQuote(root, "Bahnhofstrasse 1, 8001 Zurich");
    expect(marked(root)).toBe("Bahnhof|strasse 1,   8001| Zurich");
    expect(first?.textContent).toBe("Bahnhof");
    // The text itself is unchanged
    expect(root.textContent).toBe("Registered office: Bahnhofstrasse 1,   8001 Zurich");
  });

  it("marks each piece of a quote cut by an ellipsis", () => {
    const root = page("<p>Policy no. 4411</p><p>Sum insured: CHF 5 000 000</p>");
    markQuote(root, "Policy no. 4411 … CHF 5 000 000");
    expect(marked(root)).toBe("Policy no. 4411|CHF 5 000 000");
  });

  it("marks the cells of a table row quoted as one line, in their order", () => {
    // Given "60 %" also earlier in the document
    const root = page(
      "<p>Growth 60 %</p><table><tr><td>Founders (Marc Keller)</td><td>60 %</td><td>Swiss</td></tr></table>",
    );
    markQuote(root, "Founders (Marc Keller) | 60 % | Swiss");
    expect(marked(root)).toBe("Founders (Marc Keller)|60 %|Swiss");
    expect(root.querySelector("p mark")).toBeNull();
  });

  it("finds nothing when the quote is not in the document, and can be undone", () => {
    const root = page("<p>Alpenlogic AG</p>");
    expect(markQuote(root, "Helvetia")).toBeNull();
    markQuote(root, "Alpenlogic");
    unmarkQuotes(root);
    expect(root.innerHTML).toBe("<p>Alpenlogic AG</p>");
  });
});

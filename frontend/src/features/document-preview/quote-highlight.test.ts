import { describe, expect, it } from "vitest";
import {
  itemInQuote,
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

describe("itemInQuote (PDF text items)", () => {
  it("marks an item that is part of the quote, or that holds it", () => {
    expect(itemInQuote("Alpenlogic AG", "Company: Alpenlogic AG, Zurich")).toBe(true);
    expect(itemInQuote("Registered company: Alpenlogic AG, Zurich (CH)", "Alpenlogic AG")).toBe(
      true,
    );
  });

  it("leaves other items and short bits alone", () => {
    expect(itemInQuote("Bern", "Alpenlogic AG, Zurich")).toBe(false);
    expect(itemInQuote("AG", "Alpenlogic AG, Zurich")).toBe(false);
    expect(itemInQuote("  ", "Alpenlogic AG")).toBe(false);
  });

  it("escapes the text it puts in the text layer", () => {
    expect(markedItemHtml("<b>AG</b>", "Zurich")).toBe("&#60;b&#62;AG&#60;/b&#62;");
    expect(markedItemHtml("Alpenlogic AG", "Alpenlogic AG")).toBe("<mark>Alpenlogic AG</mark>");
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

  it("finds nothing when the quote is not in the document, and can be undone", () => {
    const root = page("<p>Alpenlogic AG</p>");
    expect(markQuote(root, "Helvetia")).toBeNull();
    markQuote(root, "Alpenlogic");
    unmarkQuotes(root);
    expect(root.innerHTML).toBe("<p>Alpenlogic AG</p>");
  });
});

import { readFileSync } from "node:fs";
import { renderAsync } from "docx-preview";
import { annex4Field } from "@/shared/test/fixtures";
import { findParagraph, writePreviewValue, type DocxLocator } from "./docx-locator";

const ANNEX_4 = "../forms/Annex_4_Conditions of Participation and Company Self-Declaration.docx";

/** The real Annex 4, rendered by docx-preview as the Live fill screen does. */
async function renderAnnex4(): Promise<HTMLElement> {
  const container = document.createElement("div");
  document.body.replaceChildren(container);
  await renderAsync(new Blob([readFileSync(ANNEX_4)]), container, undefined, { inWrapper: false });
  return container;
}

function locatorOf(key: string): DocxLocator {
  const { locator } = annex4Field(key);
  if (locator.format !== "docx") throw new Error(`${key} is not a Word field`);
  return locator;
}

function paragraphOf(root: HTMLElement, key: string): HTMLElement {
  const paragraph = findParagraph(root, locatorOf(key));
  if (!paragraph) throw new Error(`${key} not found in the rendered document`);
  return paragraph;
}

function write(root: HTMLElement, key: string, value: string | null): HTMLElement {
  return writePreviewValue(paragraphOf(root, key), locatorOf(key), value);
}

describe("finding a Word field in the rendered document", () => {
  test("each kind of place is the paragraph the export writes into", async () => {
    const root = await renderAnnex4();

    expect(paragraphOf(root, "exact_company_name").textContent).toBe("");
    expect(paragraphOf(root, "legal_form").textContent).toMatch(/^Legal form:/);
    expect(paragraphOf(root, "main_activity").textContent).toBe("Main activity:");
    expect(paragraphOf(root, "with_higher_professional_training").textContent).toBe("");
    expect(paragraphOf(root, "with_professional_training").textContent).toBe(
      "With professional training",
    );
    expect(paragraphOf(root, "remarks").textContent).toBe("");
    expect(paragraphOf(root, "place_and_date").textContent).toMatch(/^Place and date: /);
    expect(paragraphOf(root, "tender_no_type_of_work").textContent).toMatch(/^Tender \(No\. /);
  });

  test("a Yes/No answer goes into the cell next to its question", async () => {
    const root = await renderAnnex4();
    const declaration = paragraphOf(root, "have_you_paid_in_full_the_vat_or_sales_tax_due");

    expect(declaration.closest("tr")?.textContent).toContain(
      "Have you paid in full the VAT or sales tax due?",
    );
    expect(declaration.textContent).toBe("");
  });
});

describe("showing a value where the export writes it", () => {
  test("in the middle of a line, before the tabs and the signature label", async () => {
    const root = await renderAnnex4();
    const original = paragraphOf(root, "place_and_date").textContent;

    write(root, "place_and_date", "Zurich, 05.11.2026");
    const shown = paragraphOf(root, "place_and_date").textContent;

    expect(shown).toMatch(/^Place and date: Zurich, 05\.11\.2026/);
    expect(shown).toMatch(/signature\(s\):$/);
    write(root, "place_and_date", null);
    expect(paragraphOf(root, "place_and_date").textContent).toBe(original);
  });

  test("twice the same value shows it once", async () => {
    const root = await renderAnnex4();

    write(root, "main_activity", "Consulting");
    write(root, "main_activity", "Consulting");

    expect(paragraphOf(root, "main_activity").textContent).toBe("Main activity: Consulting");
  });

  test("a new value replaces the previous one, a blank one removes it", async () => {
    const root = await renderAnnex4();

    write(root, "exact_company_name", "Alpen");
    write(root, "exact_company_name", "Alpenlogic AG");
    expect(paragraphOf(root, "exact_company_name").textContent).toBe("Alpenlogic AG");

    write(root, "exact_company_name", "  ");
    expect(paragraphOf(root, "exact_company_name").textContent).toBe("");
  });

  test("in place of the dots, which come back when the value is cleared", async () => {
    const root = await renderAnnex4();
    const original = paragraphOf(root, "tender_no_type_of_work").textContent;

    write(root, "tender_no_type_of_work", "ZH-1");
    expect(paragraphOf(root, "tender_no_type_of_work").textContent).toBe(
      "Tender (No. ZH-1, type of work)",
    );

    write(root, "tender_no_type_of_work", null);
    expect(paragraphOf(root, "tender_no_type_of_work").textContent).toBe(original);
  });

  test("in a new paragraph under a label alone in its cell", async () => {
    const root = await renderAnnex4();
    const label = paragraphOf(root, "with_professional_training");

    const shown = write(root, "with_professional_training", "9");

    expect(shown).not.toBe(label);
    expect(shown.previousElementSibling).toBe(label);
    expect(shown.textContent).toBe("9");
    expect(label.textContent).toBe("With professional training");
    write(root, "with_professional_training", null);
    expect(label.nextElementSibling).toBeNull();
  });

  test("Yes/No in full, and a value on one line", async () => {
    const root = await renderAnnex4();

    write(root, "have_you_paid_in_full_the_vat_or_sales_tax_due", "yes");
    write(root, "street_postcode_city_country", "Pfingstweidstrasse 31\n8005 Zurich");

    expect(paragraphOf(root, "have_you_paid_in_full_the_vat_or_sales_tax_due").textContent).toBe(
      "Yes",
    );
    expect(paragraphOf(root, "street_postcode_city_country").textContent).toBe(
      "Pfingstweidstrasse 31 8005 Zurich",
    );
  });
});

describe("the zone of a field", () => {
  test("is the place of its value when it shares the paragraph with a label", async () => {
    const root = await renderAnnex4();
    const line = paragraphOf(root, "place_and_date");

    const place = write(root, "place_and_date", null);
    const signature = write(root, "company_stamp_and_legally_valid_signature_s", null);

    expect(place).not.toBe(line);
    expect(signature).not.toBe(line);
    expect(place).not.toBe(signature);
    expect(line.contains(place) && line.contains(signature)).toBe(true);
    expect(line.textContent).toMatch(/^Place and date: /);
  });

  test("is the paragraph when the value fills it alone", async () => {
    const root = await renderAnnex4();

    expect(write(root, "exact_company_name", null)).toBe(paragraphOf(root, "exact_company_name"));
    expect(write(root, "exact_company_name", "Alpenlogic AG")).toBe(
      paragraphOf(root, "exact_company_name"),
    );
  });
});

describe("counting what the export counts", () => {
  /** A docx-preview rendering written by hand, for structures the Annex 4 does not have. */
  function rendered(body: string): HTMLElement {
    const root = document.createElement("div");
    root.innerHTML = `<section class="docx"><article>${body}</article></section>`;
    return root;
  }
  const at = (table: number | null, row: number | null, cell: number | null, paragraph: number) =>
    ({ format: "docx", table, row, cell, paragraph, mode: "in_paragraph" }) as DocxLocator;

  test("skips the cells of a vertical merge and the room before or after a row", () => {
    // Row 0: a placeholder (w:gridBefore), then A, B. Row 1: the merge continuation, then C, D.
    const root = rendered(
      `<table><tr><td colspan="1" style="border: none;"></td><td><p>A</p></td><td><p>B</p></td></tr>` +
        `<tr><td style="display: none;"><p></p></td><td><p>C</p></td><td><p>D</p></td></tr></table>`,
    );

    expect(findParagraph(root, at(0, 0, 0, 0))?.textContent).toBe("A");
    expect(findParagraph(root, at(0, 0, 1, 0))?.textContent).toBe("B");
    expect(findParagraph(root, at(0, 1, 0, 0))?.textContent).toBe("C");
  });

  test("a paragraph the preview added does not shift the next ones", () => {
    const root = rendered(
      `<p>Intro:</p><p>Place:</p><table><tr><td><p>Staff</p><p>Remarks:</p></td></tr></table>`,
    );
    const newParagraph = (table: number | null, cell: number | null) =>
      ({ ...at(table, table === null ? null : 0, cell, 0), mode: "new_paragraph" }) as DocxLocator;

    writePreviewValue(findParagraph(root, at(0, 0, 0, 0))!, newParagraph(0, 0), "9");
    writePreviewValue(findParagraph(root, at(null, null, null, 0))!, newParagraph(null, null), "x");

    expect(findParagraph(root, at(0, 0, 0, 1))?.textContent).toBe("Remarks:");
    expect(findParagraph(root, at(null, null, null, 1))?.textContent).toBe("Place:");
  });
});

import { readdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

// The main scenario, grown slice by slice (docs/PLAN.md): today it adds the company's documents
// (the knowledge base is not seeded), previews one, auto-fills Annex 7, corrects a field, downloads the filled
// PDF and discards the answers. It runs in a dedicated, clean environment (playwright.config.ts): empty database and data.

// The demo company's documents (Alpenlogic AG, knowledge-base/GROUND_TRUTH.md).
const DEMO_DIR = path.resolve("../knowledge-base/documents");
const DEMO_FILES = readdirSync(DEMO_DIR).filter((name) => /\.(pdf|docx)$/.test(name));

test("I auto-fill Annex 7 from my documents, correct a field and download it in its original PDF layout", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { level: 1, name: "Cloud Platform Services – Canton of Zurich" }),
  ).toBeVisible();
  const forms = page.getByRole("list", { name: "Forms to complete" }).getByRole("listitem");
  await expect(forms).toHaveCount(2);
  await expect(forms.nth(0)).toContainText("Annex 4");
  await expect(forms.nth(0)).toContainText("DOCX");
  const annex7 = forms.nth(1);
  await expect(annex7).toContainText("Annex 7");
  await expect(annex7).toContainText("10 fields detected · 1 signature");

  // What the answers are drawn from: the user adds the company's documents.
  const knowledge = page.getByRole("region", { name: "Company knowledge" });
  await knowledge.getByRole("link", { name: "Manage" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Alpenlogic AG" })).toBeVisible();
  expect(DEMO_FILES).toHaveLength(11);
  await page
    .getByLabel("Choose PDF or Word documents")
    .setInputFiles(DEMO_FILES.map((name) => path.join(DEMO_DIR, name)));
  // Listed at once while processed, then indexed one by one, without reloading the page.
  const documents = page.getByRole("table", { name: "Documents" }).getByRole("row");
  const added = (name: string) => documents.filter({ hasText: name });
  await expect(added(DEMO_FILES[0])).toContainText(/Processing|Indexed/);
  for (const name of DEMO_FILES) {
    await expect(added(name)).toContainText("Indexed", { timeout: 60_000 });
  }

  // A document opens in place, its pages rendered.
  await page.getByRole("button", { name: "Preview Commercial register extract" }).click();
  const viewer = page.getByRole("dialog", { name: "Commercial register extract" });
  await expect(viewer.getByLabel("Page 2").locator("canvas")).toBeVisible();
  await expect(viewer.getByRole("link", { name: "Download" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(viewer).toBeHidden();
  await page.getByRole("list", { name: "Main" }).getByRole("link", { name: "Tenders" }).click();

  // Auto-fill Annex 7: the Setup dialog recalls what the answers are drawn from.
  await annex7.getByRole("button", { name: "Auto-fill" }).click();
  const setup = page.getByRole("dialog", { name: /^Auto-fill / });
  await expect(setup).toContainText("Company knowledge · 11 documents");
  await setup.getByRole("button", { name: "Start" }).click();
  await expect(page).toHaveURL(/\/forms\/\d+\/fill$/);

  // The form fills itself field by field; the recorded run answers all 9 fillable fields.
  const fields = page.getByRole("list", { name: "Fields" });
  await expect(fields.getByRole("listitem", { name: /./ })).toHaveCount(10);
  // (The "9 of 9 fields filled in N seconds" line only shows to a page watching the stream live; the
  // recorded fill ends in milliseconds, so the stable check is the review summary.)
  await expect(page.getByText("9 / 9 filled · 0 empty · 0 doubts")).toBeVisible({
    timeout: 20_000,
  });
  const preview = page.getByRole("region", { name: "Form preview" });
  await expect(preview.locator("canvas")).toBeVisible();
  await expect(preview.locator("[data-field-id]")).toHaveCount(10);

  // An automatic answer shows its source: document name, page and quote.
  const address = fields.getByRole("textbox", { name: "Business address" });
  await expect(address).toHaveValue("Pfingstweidstrasse 31, 8005 Zurich");
  await address.click();
  const addressCard = fields.getByRole("listitem", { name: "Business address" });
  await expect(addressCard.getByText("Filled automatically")).toBeVisible();
  await expect(addressCard.getByText("Commercial register extract, page 1")).toBeVisible();
  await expect(addressCard.locator("blockquote")).toContainText(
    "Pfingstweidstrasse 31, 8005 Zurich",
  );

  // Correct one field by hand: it is saved and shown on the form.
  await address.clear();
  await address.pressSequentially("Pfingstweidstrasse 31");
  await expect(preview.getByText("Pfingstweidstrasse 31", { exact: true })).toBeVisible();
  await address.pressSequentially(", 8005 Zürich");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("status")).toHaveText(/saved/i);
  await expect(preview.getByText("Pfingstweidstrasse 31, 8005 Zürich")).toBeVisible();

  // Export, over the form: the download is the filled PDF, under the original file name.
  await page.getByRole("button", { name: "Export PDF" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Sign by hand: Signature(s)")).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("link", { name: "Download PDF" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe(
    "Annex_7_Self-Declaration_Art29c_Ukraine_Ordinance.pdf",
  );
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk as Buffer);
  const pdf = Buffer.concat(chunks);
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");

  // Discard the answers from the tender: the card is back to "Not started".
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.goto("/");
  const started = page
    .getByRole("list", { name: "Forms to complete" })
    .getByRole("listitem")
    .nth(1);
  await expect(started.getByRole("link", { name: "Continue review" })).toBeVisible();
  await started.getByRole("button", { name: "More actions" }).click();
  await page.getByRole("menuitem", { name: "Discard answers" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Discard", exact: true }).click();
  await expect(started).toContainText("Not started");
  await expect(started.getByRole("button", { name: "Auto-fill" })).toBeVisible();
});

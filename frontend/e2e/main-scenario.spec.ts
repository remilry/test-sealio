import { expect, test } from "@playwright/test";

// The main scenario, grown slice by slice (docs/PLAN.md): today it checks the company knowledge,
// fills Annex 7 by hand and downloads the filled PDF. The back may be a dev server with data already entered: the scenario
// accepts a form already in review and overwrites the values it types.
test("I fill Annex 7 by hand and download it in its original PDF layout", async ({ page }) => {
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

  // What the AI answers from: the company's 11 documents, all indexed at startup.
  const knowledge = page.getByRole("region", { name: "Company knowledge" });
  await expect(knowledge).toContainText("11documents");
  await knowledge.getByRole("link", { name: "Manage" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Alpenlogic AG" })).toBeVisible();
  const documents = page.getByRole("table", { name: "Documents" }).getByRole("row");
  // 11 documents and the header row.
  await expect(documents).toHaveCount(12);
  await expect(documents.filter({ hasText: "Indexed" })).toHaveCount(11);
  await page.getByRole("list", { name: "Main" }).getByRole("link", { name: "Tenders" }).click();

  // Open Annex 7: its detected fields are listed and drawn on the original form.
  await annex7.getByRole("link", { name: /Fill with AI|Continue review/ }).click();
  await expect(page).toHaveURL(/\/forms\/\d+\/fill$/);
  const fields = page.getByRole("list", { name: "Fields" });
  await expect(fields.getByRole("listitem")).toHaveCount(10);
  const preview = page.getByRole("region", { name: "Form preview" });
  await expect(preview.locator("canvas")).toBeVisible();
  await expect(preview.locator("[data-field-id]")).toHaveCount(10);

  // Type two values: each is saved and shown on the form.
  await fields.getByRole("textbox", { name: "Name and legal form" }).fill("Alpenlogic AG");
  await page.keyboard.press("Enter");
  const address = fields.getByRole("textbox", { name: "Business address" });
  await expect(address).toBeFocused();
  // Replaces a value left by a previous run; the document follows each keystroke.
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
  expect(Buffer.concat(chunks).subarray(0, 5).toString()).toBe("%PDF-");
});

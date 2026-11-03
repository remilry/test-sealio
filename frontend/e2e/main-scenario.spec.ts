import { expect, test } from "@playwright/test";

// The main scenario, grown slice by slice (docs/PLAN.md): today it stops at the Tender page.
test("I open the app and see the tender with the two buyer forms to complete", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { level: 1, name: "Cloud Platform Services – Canton of Zurich" }),
  ).toBeVisible();
  const forms = page.getByRole("list", { name: "Forms to complete" }).getByRole("listitem");
  await expect(forms).toHaveCount(2);
  await expect(forms.nth(0)).toContainText("Annex 4");
  await expect(forms.nth(0)).toContainText("DOCX");
  await expect(forms.nth(1)).toContainText("Annex 7");
  await expect(forms.nth(1)).toContainText("PDF");

  await page.getByRole("link", { name: /Cloud Platform Services/ }).click();
  await expect(page).toHaveURL(/\/tenders\/\d+$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Cloud Platform Services – Canton of Zurich",
  );
});

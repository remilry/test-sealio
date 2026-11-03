import { expect, test } from "@playwright/test";

// Tooling check, replaced by the main-scenario test in step 4.
test("the app starts", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Formpilot" })).toBeVisible();
});

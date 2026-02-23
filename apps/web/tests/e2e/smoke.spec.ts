import { expect, test } from "@playwright/test";

test("loads home page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "OmniFlow AI" })).toBeVisible();
});

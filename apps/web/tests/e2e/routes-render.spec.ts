import { expect, test } from "@playwright/test";

const CRITICAL_ROUTES = [
  "/dashboard",
  "/campaigns",
  "/content",
  "/publish/jobs",
  "/ads",
  "/analytics",
  "/inbox",
  "/leads",
  "/optimization",
  "/presence",
  "/seo",
  "/reputation",
  "/settings/org",
  "/settings/verticals",
  "/settings/integrations",
  "/automations",
  "/runs",
  "/agents",
];

test("critical console routes render without 404/runtime error shell", async ({ page }) => {
  for (const path of CRITICAL_ROUTES) {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).not.toContainText("This page could not be found");
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("500");
  }
});

import { expect, test } from "@playwright/test";

const optimizationRoutes: Array<{ path: string; heading: string }> = [
  { path: "/optimization", heading: "Optimization Engine" },
  { path: "/optimization/leads", heading: "Predictive Lead Scoring" },
  { path: "/optimization/campaigns", heading: "Post Timing Optimization" },
  { path: "/optimization/ads", heading: "Ads Budget Recommendations" },
  { path: "/optimization/workflows", heading: "Workflow Optimization Suggestions" },
];

test("optimization routes render key headings", async ({ page }) => {
  for (const route of optimizationRoutes) {
    await page.goto(route.path, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
    await expect(page.getByText("Something went wrong", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Page not found", { exact: false })).toHaveCount(0);
  }
});

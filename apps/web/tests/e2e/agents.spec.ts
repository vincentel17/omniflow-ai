import { expect, test } from "@playwright/test";

const routes: Array<{ path: string; heading: string }> = [
  { path: "/automations/agents", heading: "Agents" },
  { path: "/automations/agents/runs", heading: "Agent Runs" },
];

test("phase16 agents routes render key headings", async ({ page }) => {
  for (const route of routes) {
    await page.goto(route.path, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
    await expect(page.getByText("Something went wrong", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Page not found", { exact: false })).toHaveCount(0);
  }
});

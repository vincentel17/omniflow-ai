import { expect, test } from "@playwright/test";

test("unauthenticated user is redirected from dashboard to login", async ({ page }) => {
  await page.goto("/dashboard?__auth=1", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/auth\/login/);
  await expect(page.getByRole("heading", { name: "Sign in to OmniFlow" })).toBeVisible();
});

test("session-authenticated user can reach dashboard", async ({ page, context }) => {
  const sessionPayload = Buffer.from(
    JSON.stringify({
      user_id: "playwright-user",
      org_id: "playwright-org",
      role: "owner"
    })
  )
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");

  await context.addCookies([
    {
      name: "omniflow_session_ctx",
      value: sessionPayload,
      domain: "127.0.0.1",
      path: "/"
    }
  ]);
  await page.goto("/auth/login", { waitUntil: "domcontentloaded" });
  await page.goto("/dashboard?__auth=1", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/dashboard\?__auth=1/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

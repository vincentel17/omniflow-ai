import { expect, test } from "@playwright/test";

test("authenticated user can logout and is redirected to login", async ({ page, context }) => {
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

  await page.goto("/dashboard?__auth=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.getByTestId("app-logout").click();
  await expect(page).toHaveURL(/\/auth\/login/);

  await page.goto("/dashboard?__auth=1", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/auth\/login/);
});

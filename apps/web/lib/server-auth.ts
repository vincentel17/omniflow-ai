import { redirect } from "next/navigation";

import { getRequestSessionContext, type SessionContext } from "./dev-context";

export async function requireAuthSession(): Promise<SessionContext> {
  if (process.env.PLAYWRIGHT === "1" && process.env.PLAYWRIGHT_WEB_SERVER === "1") {
    return {
      authenticated: true,
      user_id: "playwright-user",
      org_id: "playwright-org",
      role: "owner"
    };
  }

  const session = await getRequestSessionContext();
  if (!session?.authenticated) {
    redirect("/auth");
  }
  return session;
}

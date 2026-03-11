import type { NextRequest } from "next/server";
import { redirect } from "next/navigation";

import { getRequestSessionContext, type SessionContext } from "./dev-context";

function hasCookieValue(request: NextRequest, key: string): boolean {
  if (!key) {
    return false;
  }
  const value = request.cookies.get(key)?.value;
  return typeof value === "string" && value.trim().length > 0;
}

export function hasValidSession(request: NextRequest): boolean {
  const configuredAuthCookie = process.env.AUTH_COOKIE_NAME ?? "";
  return (
    hasCookieValue(request, "omniflow_session") ||
    hasCookieValue(request, "omniflow_session_ctx") ||
    hasCookieValue(request, configuredAuthCookie)
  );
}

export async function getCurrentUser(): Promise<SessionContext> {
  if (process.env.PLAYWRIGHT === "1" && process.env.PLAYWRIGHT_WEB_SERVER === "1") {
    return {
      authenticated: true,
      user_id: "playwright-user",
      org_id: "playwright-org",
      role: "owner"
    };
  }

  const session = await getRequestSessionContext();
  if (!session?.authenticated || !session.user_id || !session.org_id || !session.role) {
    redirect("/auth/login");
  }
  return session;
}

export async function requireAuthSession(): Promise<SessionContext> {
  return getCurrentUser();
}

import { buildDevContext, getDefaultDevContext, normalizePreviewSelection, parseCookieHeader, type DevContext } from "./preview-context";

export type { DevContext } from "./preview-context";
export type SessionContext = {
  authenticated: boolean;
  user_id: string;
  org_id: string;
  role: string;
};

export function getDevContext(): DevContext {
  if (typeof window === "undefined") {
    return getDefaultDevContext();
  }

  const cookies = parseCookieHeader(window.document.cookie);
  const { previewOrg, previewRole } = normalizePreviewSelection(cookies.omniflow_preview_org, cookies.omniflow_preview_role);
  return buildDevContext(previewOrg, previewRole);
}

export async function getRequestDevContext(): Promise<DevContext> {
  if (typeof window !== "undefined") {
    return getDevContext();
  }

  try {
    const { cookies } = await import("next/headers");
    const store = await cookies();
    const previewOrg = store.get("omniflow_preview_org")?.value;
    const previewRole = store.get("omniflow_preview_role")?.value;
    const selection = normalizePreviewSelection(previewOrg, previewRole);
    return buildDevContext(selection.previewOrg, selection.previewRole);
  } catch {
    return getDefaultDevContext();
  }
}

export async function getRequestSessionContext(): Promise<SessionContext | null> {
  if (typeof window !== "undefined") {
    return null;
  }

  try {
    const { cookies } = await import("next/headers");
    const store = await cookies();
    const cookieHeader = store
      .getAll()
      .map((entry) => `${entry.name}=${entry.value}`)
      .join("; ");
    if (!cookieHeader) {
      return null;
    }

    const response = await fetch(`${getApiBaseUrl()}/auth/session`, {
      cache: "no-store",
      headers: { Cookie: cookieHeader }
    });
    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as {
      authenticated?: boolean;
      session?: { user_id?: string; org_id?: string; role?: string } | null;
    };
    if (!payload.authenticated || !payload.session?.user_id || !payload.session.org_id || !payload.session.role) {
      return null;
    }

    return {
      authenticated: true,
      user_id: payload.session.user_id,
      org_id: payload.session.org_id,
      role: payload.session.role
    };
  } catch {
    return null;
  }
}

export function getApiBaseUrl(): string {
  const isServer = typeof window === "undefined";

  if (isServer) {
    if (process.env.API_BASE_URL) {
      return process.env.API_BASE_URL;
    }

    return "http://api:8000";
  }

  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  if (process.env.API_BASE_URL) {
    return process.env.API_BASE_URL;
  }

  return "http://localhost:18000";
}

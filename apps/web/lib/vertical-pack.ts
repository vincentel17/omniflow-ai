import { getApiBaseUrl } from "./dev-context";

type SessionLike = {
  org_id?: string;
} | null | undefined;

type CurrentPack = {
  pack_slug: string;
};

export async function getCurrentPackSlug(): Promise<string | null> {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json"
    };

    if (typeof window === "undefined") {
      const { cookies } = await import("next/headers");
      const store = await cookies();
      const cookieHeader = store
        .getAll()
        .map((entry) => `${entry.name}=${entry.value}`)
        .join("; ");
      if (cookieHeader) {
        headers.Cookie = cookieHeader;
      }
    }

    const response = await fetch(`${getApiBaseUrl()}/verticals/current`, {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(1000)
    });
    if (!response.ok) {
      return null;
    }
    const current = (await response.json()) as CurrentPack;
    return current.pack_slug;
  } catch {
    return null;
  }
}

export async function getCurrentPackSlugForSession(session: SessionLike): Promise<string | null> {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json"
    };

    if (typeof window === "undefined") {
      const { cookies } = await import("next/headers");
      const store = await cookies();
      const cookieHeader = store
        .getAll()
        .map((entry) => `${entry.name}=${entry.value}`)
        .join("; ");
      if (cookieHeader) {
        headers.Cookie = cookieHeader;
      }
    }

    if (session?.org_id) {
      headers["X-Org-Id"] = session.org_id;
      headers["x-org-id"] = session.org_id;
    }

    const response = await fetch(`${getApiBaseUrl()}/verticals/current`, {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(1000)
    });
    if (!response.ok) {
      return null;
    }
    const current = (await response.json()) as CurrentPack;
    return current.pack_slug;
  } catch {
    return null;
  }
}

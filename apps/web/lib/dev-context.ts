export type SessionContext = {
  authenticated: boolean;
  user_id: string;
  org_id: string;
  role: string;
};

export async function getRequestSessionContext(): Promise<SessionContext | null> {
  if (typeof window !== "undefined") {
    return null;
  }

  try {
    const { cookies } = await import("next/headers");
    const store = await cookies();
    const mirrored = store.get("omniflow_session_ctx")?.value;
    if (mirrored) {
      const parsed = parseMirroredSession(mirrored);
      if (parsed) {
        return parsed;
      }
    }

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

function parseMirroredSession(value: string): SessionContext | null {
  try {
    const decoded = Buffer.from(value, "base64url").toString("utf8");
    const payload = JSON.parse(decoded) as Partial<SessionContext>;
    if (!payload.user_id || !payload.org_id || !payload.role) {
      return null;
    }
    return {
      authenticated: true,
      user_id: payload.user_id,
      org_id: payload.org_id,
      role: payload.role
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

export type DevContext = {
  userId: string;
  orgId: string;
  role: "owner" | "admin" | "member" | "agent";
};

const defaultContext: DevContext = {
  userId: process.env.NEXT_PUBLIC_DEV_USER_ID ?? "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  orgId: process.env.NEXT_PUBLIC_DEV_ORG_ID ?? "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  role: "owner"
};

export function getDevContext(): DevContext {
  return defaultContext;
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

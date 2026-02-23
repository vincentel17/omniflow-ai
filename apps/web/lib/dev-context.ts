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
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

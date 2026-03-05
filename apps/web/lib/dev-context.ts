import { buildDevContext, getDefaultDevContext, normalizePreviewSelection, parseCookieHeader, type DevContext } from "./preview-context";

export type { DevContext } from "./preview-context";

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

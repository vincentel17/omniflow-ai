import { getApiBaseUrl, getDevContext } from "./dev-context";

type CurrentPack = {
  pack_slug: string;
};

export async function getCurrentPackSlug(): Promise<string | null> {
  try {
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/verticals/current`, {
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      },
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

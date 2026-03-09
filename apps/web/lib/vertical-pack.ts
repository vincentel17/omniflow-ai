import { getApiBaseUrl } from "./dev-context";

type CurrentPack = {
  pack_slug: string;
};

export async function getCurrentPackSlug(): Promise<string | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/verticals/current`, {
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
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

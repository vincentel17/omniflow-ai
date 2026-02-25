import { getApiBaseUrl, getDevContext } from "./dev-context";

export type ApiMethod = "GET" | "POST" | "PATCH" | "DELETE";

export type ApiError = {
  status: number;
  message: string;
  path: string;
};

type FetchOptions = {
  method?: ApiMethod;
  body?: unknown;
};

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const context = getDevContext();
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Omniflow-User-Id": context.userId,
      "X-Omniflow-Org-Id": context.orgId,
      "X-Omniflow-Role": context.role
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store"
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Ignore parse failures and keep generic message.
    }

    throw <ApiError>{
      status: response.status,
      message,
      path
    };
  }

  return (await response.json()) as T;
}

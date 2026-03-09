export async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string;
      message?: string;
      error?: string;
      request_id?: string;
    };
    const detail = payload.detail ?? payload.message ?? payload.error;
    if (!detail) {
      return `${fallback} (${response.status})`;
    }
    return payload.request_id ? `${detail} [request_id=${payload.request_id}]` : detail;
  } catch {
    return `${fallback} (${response.status})`;
  }
}

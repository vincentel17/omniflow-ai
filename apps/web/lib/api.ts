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

export type ComplianceRetentionPolicy = {
  id: string;
  org_id: string;
  entity_type: string;
  retention_days: number;
  hard_delete_after_days: number;
  created_at: string;
};

export type ComplianceDsarRequest = {
  id: string;
  org_id: string;
  request_type: string;
  subject_identifier: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
  export_ref: string | null;
  created_at: string;
};

export type ComplianceRbacMatrix = {
  roles: Record<string, string[]>;
};

export type ComplianceEvidenceBundle = {
  from_date: string;
  to_date: string;
  include_pii: boolean;
  bundle_json: Record<string, unknown>;
};

export async function getComplianceMode(): Promise<{ compliance_mode: string }> {
  return apiFetch<{ compliance_mode: string }>("/compliance/mode");
}

export async function getComplianceRetentionPolicies(): Promise<ComplianceRetentionPolicy[]> {
  return apiFetch<ComplianceRetentionPolicy[]>("/compliance/retention");
}

export async function listComplianceDsarRequests(limit = 20, offset = 0): Promise<ComplianceDsarRequest[]> {
  return apiFetch<ComplianceDsarRequest[]>(`/compliance/dsar?limit=${limit}&offset=${offset}`);
}

export async function getComplianceRbacMatrix(): Promise<ComplianceRbacMatrix> {
  return apiFetch<ComplianceRbacMatrix>("/compliance/rbac-matrix");
}

export async function getComplianceEvidenceBundle(fromDate: string, toDate: string, includePii: boolean): Promise<ComplianceEvidenceBundle> {
  return apiFetch<ComplianceEvidenceBundle>(
    `/compliance/evidence-bundle?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}&include_pii=${includePii}`,
  );
}

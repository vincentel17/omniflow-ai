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

export type OptimizationModel = {
  id: string;
  org_id: string;
  name: string;
  version: string;
  trained_at: string;
  training_window: string;
  metrics_json: Record<string, unknown>;
  status: string;
  created_at: string;
};

export type PredictiveLeadScore = {
  id: string;
  org_id: string;
  lead_id: string;
  model_version: string;
  score_probability: number;
  feature_importance_json: Record<string, number>;
  predicted_stage_probability_json: Record<string, number>;
  explanation: string;
  final_score: number;
  scored_at: string;
};

export type PredictiveLeadScoreListItem = {
  id: string;
  lead_id: string;
  model_version: string;
  score_probability: number;
  explanation: string;
  scored_at: string;
};

export type PostingOptimization = {
  id: string;
  org_id: string;
  channel: string;
  best_day_of_week: number;
  best_hour: number;
  confidence_score: number;
  model_version: string;
  explanation: string;
  updated_at: string;
};

export type NurtureRecommendation = {
  recommended_delays_minutes: number[];
  explanation: string;
};

export type AdBudgetRecommendation = {
  id: string;
  org_id: string;
  campaign_id: string;
  recommended_daily_budget: number;
  reasoning_json: Record<string, string | number>;
  projected_cpl: number;
  model_version: string;
  explanation: string;
  created_at: string;
};

export type WorkflowOptimizationSuggestion = {
  workflow_key: string;
  suggestion: string;
  priority: string;
};

export type NextBestAction = {
  action_type: string;
  rationale: string;
  expected_uplift: number;
  confidence_score: number;
};

export type OptimizationSettings = {
  enable_predictive_scoring: boolean;
  enable_post_timing_optimization: boolean;
  enable_nurture_optimization: boolean;
  enable_ad_budget_recommendations: boolean;
  auto_apply_low_risk_optimizations: boolean;
};

export async function getOptimizationSettings(): Promise<OptimizationSettings> {
  return apiFetch<OptimizationSettings>("/optimization/settings");
}

export async function listOptimizationModels(): Promise<OptimizationModel[]> {
  return apiFetch<OptimizationModel[]>("/optimization/models");
}

export async function listPredictiveLeadScores(limit = 25, offset = 0): Promise<PredictiveLeadScoreListItem[]> {
  return apiFetch<PredictiveLeadScoreListItem[]>(`/optimization/leads?limit=${limit}&offset=${offset}`);
}

export async function listPostingOptimizations(channel = "meta"): Promise<PostingOptimization[]> {
  return apiFetch<PostingOptimization[]>(`/optimization/campaigns?channel=${encodeURIComponent(channel)}`);
}

export async function getNurtureRecommendations(): Promise<NurtureRecommendation> {
  return apiFetch<NurtureRecommendation>("/optimization/nurture/recommendations");
}

export async function listAdBudgetRecommendations(): Promise<AdBudgetRecommendation[]> {
  return apiFetch<AdBudgetRecommendation[]>("/optimization/ads?limit=20");
}

export async function listWorkflowOptimizationSuggestions(): Promise<WorkflowOptimizationSuggestion[]> {
  return apiFetch<WorkflowOptimizationSuggestion[]>("/optimization/workflows");
}

export async function getNextBestAction(entityType: string, id: string): Promise<NextBestAction> {
  return apiFetch<NextBestAction>(`/optimization/next-best-action/${encodeURIComponent(entityType)}/${encodeURIComponent(id)}`);
}

export async function scoreLeadPredictive(leadId: string): Promise<PredictiveLeadScore> {
  return apiFetch<PredictiveLeadScore>(`/optimization/lead-score/${encodeURIComponent(leadId)}`, { method: "POST" });
}


export type VerticalPackManifest = {
  slug: string;
  name: string;
  version: string;
  compatible_core_version: string;
  features: Record<string, boolean>;
  checksum: string;
  status: string;
};

export type AdminVerticalRegistryItem = {
  slug: string;
  version: string;
  status: string;
  checksum: string;
  installed_at: string;
};

export async function listVerticalPacks(): Promise<VerticalPackManifest[]> {
  return apiFetch<VerticalPackManifest[]>("/verticals/available");
}

export async function getVerticalPackManifest(slug: string): Promise<VerticalPackManifest> {
  return apiFetch<VerticalPackManifest>(`/verticals/${encodeURIComponent(slug)}/manifest`);
}

export async function listAdminVerticalRegistry(): Promise<AdminVerticalRegistryItem[]> {
  return apiFetch<AdminVerticalRegistryItem[]>("/admin/verticals");
}

export type AdminVerticalPerformanceItem = {
  pack_slug: string;
  org_count: number;
  funnel_events: number;
  revenue_events: number;
  automation_events: number;
  predictive_events: number;
};

export async function listAdminVerticalPerformance(): Promise<AdminVerticalPerformanceItem[]> {
  return apiFetch<AdminVerticalPerformanceItem[]>("/admin/vertical-performance");
}



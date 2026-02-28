import { apiFetch, type ApiError } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/primitives";

type BillingOverview = {
  mrr_usd: number;
  arr_projection_usd: number;
  active_subscriptions: number;
  churn_count: number;
};

type OrgSummary = {
  id: string;
  name: string;
  org_status: string;
};

type AdminState = {
  overview: BillingOverview | null;
  orgs: OrgSummary[];
  notice: string | null;
};

async function getAdminState(): Promise<AdminState> {
  try {
    const [overview, orgs] = await Promise.all([
      apiFetch<BillingOverview>("/admin/billing/overview"),
      apiFetch<OrgSummary[]>("/admin/orgs?limit=20&offset=0"),
    ]);
    return { overview, orgs, notice: null };
  } catch (error) {
    const apiError = error as ApiError;
    return {
      overview: null,
      orgs: [],
      notice: apiError?.message ?? "Global admin access is required for this page.",
    };
  }
}

export default async function AdminPage() {
  const state = await getAdminState();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Global Admin Console</h1>
        <p className="page-subtitle">Cross-tenant operations, revenue overview, and controlled support access.</p>`r`n        <p className="mt-2 text-sm">`r`n          <a className="text-[rgb(var(--accent))] hover:underline" href="/admin/verticals">`r`n            View vertical registry`r`n          </a>`r`n        </p>
      </section>

      {state.notice ? <section className="surface-card p-4 text-sm text-amber-300">{state.notice}</section> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardHeader><CardTitle>MRR</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">${state.overview?.mrr_usd ?? 0}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>ARR Projection</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">${state.overview?.arr_projection_usd ?? 0}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Active Subscriptions</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{state.overview?.active_subscriptions ?? 0}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Churn Count</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{state.overview?.churn_count ?? 0}</p></CardContent></Card>
      </section>

      <section className="surface-card p-4">
        <h2 className="text-lg font-semibold">Organizations</h2>
        <ul className="mt-3 space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
          {state.orgs.length === 0 ? <li>No organization rows available for this user context.</li> : null}
          {state.orgs.map((org) => (
            <li key={org.id}><span className="font-mono text-xs">{org.id}</span> | {org.name} | {org.org_status}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}



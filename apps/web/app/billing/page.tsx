import { apiFetch } from "../../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/primitives";

type Subscription = {
  id: string;
  org_id: string;
  plan_id: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
};

type Plan = {
  id: string;
  name: string;
  price_monthly_usd: number;
  price_yearly_usd: number;
};

async function getBillingData(): Promise<{ subscription: Subscription | null; plans: Plan[] }> {
  try {
    const [subscription, plans] = await Promise.all([
      apiFetch<Subscription>("/billing/subscription"),
      apiFetch<Plan[]>("/billing/plans"),
    ]);
    return { subscription, plans };
  } catch {
    return { subscription: null, plans: [] };
  }
}

export default async function BillingPage() {
  const { subscription, plans } = await getBillingData();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Billing</h1>
        <p className="page-subtitle">Plan status, subscription state, and deterministic mock billing controls.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardHeader><CardTitle>Subscription</CardTitle></CardHeader><CardContent><p className="text-2xl font-semibold">{subscription?.status ?? "Not set"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Plan ID</CardTitle></CardHeader><CardContent><p className="font-mono text-xs">{subscription?.plan_id ?? "-"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Period Start</CardTitle></CardHeader><CardContent><p>{subscription?.current_period_start ?? "-"}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Period End</CardTitle></CardHeader><CardContent><p>{subscription?.current_period_end ?? "-"}</p></CardContent></Card>
      </section>

      <section className="surface-card p-4">
        <h2 className="text-lg font-semibold">Available Plans</h2>
        <ul className="mt-3 space-y-2 text-sm text-[rgb(var(--muted-foreground))]">
          {plans.length === 0 ? <li>No plans loaded.</li> : null}
          {plans.map((plan) => (
            <li key={plan.id}>{plan.name}: ${plan.price_monthly_usd}/mo | ${plan.price_yearly_usd}/yr</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

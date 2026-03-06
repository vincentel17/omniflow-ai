import { apiFetch } from "../../../../lib/api";

type DiagnosticsSummary = {
  connector_mode: string;
  ai_mode: string;
  ads_mode: string;
  live_ready: boolean;
  env_checks: Array<{ key: string; required_for_live: boolean; present: boolean }>;
  accounts_linked: number;
  last_sync_at: string | null;
  last_error: string | null;
  gbp_last_sync_at: string | null;
  gbp_last_error: string | null;
};

const GBP_ENV_KEYS = [
  "PROVIDER_ENABLE_GBP",
  "GOOGLE_CLIENT_ID",
  "GOOGLE_CLIENT_SECRET",
  "OAUTH_REDIRECT_URI",
  "TOKEN_ENCRYPTION_KEY"
] as const;

async function getDiagnosticsSummary(): Promise<DiagnosticsSummary | null> {
  try {
    return await apiFetch<DiagnosticsSummary>("/connectors/diagnostics/summary");
  } catch {
    return null;
  }
}

export default async function IntegrationsDiagnosticsPage() {
  const diagnostics = await getDiagnosticsSummary();
  const gbpChecks = diagnostics
    ? diagnostics.env_checks.filter((item) =>
        GBP_ENV_KEYS.includes(item.key as (typeof GBP_ENV_KEYS)[number])
      )
    : [];
  const gbpEnabled = gbpChecks.find((item) => item.key === "PROVIDER_ENABLE_GBP")?.present ?? false;
  const gbpReady = gbpChecks
    .filter((item) => item.key !== "PROVIDER_ENABLE_GBP")
    .every((item) => item.present);

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Integration Diagnostics</h1>
        <p className="page-subtitle">
          Current connector mode, environment readiness, and sanitized integration health signals.
        </p>
      </section>

      <section className="surface-card p-6">
        {!diagnostics ? (
          <p className="text-sm text-[rgb(var(--muted-foreground))]">Diagnostics unavailable.</p>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <article className="rounded-2xl border border-[rgb(var(--border))] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                  Connector mode
                </p>
                <p className="mt-2 text-lg font-semibold">{diagnostics.connector_mode}</p>
              </article>
              <article className="rounded-2xl border border-[rgb(var(--border))] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                  AI mode
                </p>
                <p className="mt-2 text-lg font-semibold">{diagnostics.ai_mode}</p>
              </article>
              <article className="rounded-2xl border border-[rgb(var(--border))] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                  Ads mode
                </p>
                <p className="mt-2 text-lg font-semibold">{diagnostics.ads_mode}</p>
              </article>
              <article className="rounded-2xl border border-[rgb(var(--border))] p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                  Live readiness
                </p>
                <p className="mt-2 text-lg font-semibold">{diagnostics.live_ready ? "Ready" : "Mock-only"}</p>
              </article>
            </div>

            <div className="rounded-2xl border border-[rgb(var(--border))] p-4 text-sm text-[rgb(var(--muted-foreground))]">
              <p>Accounts linked: {diagnostics.accounts_linked}</p>
              <p>Last sync: {diagnostics.last_sync_at ?? "n/a"}</p>
              <p>Last error: {diagnostics.last_error ?? "n/a"}</p>
            </div>

            <div className="rounded-2xl border border-[rgb(var(--border))] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-[rgb(var(--muted-foreground))]">
                    Google Business Profile
                  </p>
                  <p className="mt-2 text-lg font-semibold">
                    {diagnostics.connector_mode === "live" && gbpEnabled ? "Live enabled" : "Mock only"}
                  </p>
                </div>
                <div className="text-sm text-[rgb(var(--muted-foreground))]">
                  <p>Provider enabled: {gbpEnabled ? "yes" : "no"}</p>
                  <p>Env readiness: {gbpReady ? "ready" : "missing required values"}</p>
                  <p>Last sync: {diagnostics.gbp_last_sync_at ?? "n/a"}</p>
                  <p>Last error: {diagnostics.gbp_last_error ?? "n/a"}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {gbpChecks.map((item) => (
                  <article className="rounded-2xl border border-[rgb(var(--border))] p-4" key={item.key}>
                    <p className="text-sm font-semibold">{item.key}</p>
                    <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">
                      {item.present ? "present" : "missing"}
                    </p>
                  </article>
                ))}
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {diagnostics.env_checks.map((item) => (
                <article className="rounded-2xl border border-[rgb(var(--border))] p-4" key={item.key}>
                  <p className="text-sm font-semibold">{item.key}</p>
                  <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">
                    {item.present ? "present" : "missing"} | {item.required_for_live ? "required for live" : "optional"}
                  </p>
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

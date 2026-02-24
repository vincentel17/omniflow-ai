import Link from "next/link";

import { apiFetch } from "../../../../lib/api";
import { IntegrationDiagnosticsClient } from "./integration-diagnostics-client";

type Diagnostics = {
  id: string;
  provider: string;
  account_ref: string;
  account_status: string;
  scopes: string[];
  expires_at: string | null;
  health_status: string;
  breaker_state: string;
  last_error_msg: string | null;
  last_http_status: number | null;
  last_provider_error_code: string | null;
  last_rate_limit_reset_at: string | null;
  reauth_required: boolean;
  mode_effective: string;
};

async function getDiagnostics(accountId: string): Promise<Diagnostics | null> {
  try {
    return await apiFetch<Diagnostics>(`/connectors/accounts/${accountId}/diagnostics`);
  } catch {
    return null;
  }
}

export default async function IntegrationDiagnosticsPage({ params }: { params: Promise<{ accountId: string }> }) {
  const resolvedParams = await params;
  const diagnostics = await getDiagnostics(resolvedParams.accountId);

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <Link className="text-sm underline" href="/settings/integrations">
        Back to Integrations
      </Link>
      <h1 className="mt-2 text-3xl font-semibold">Integration Diagnostics</h1>
      {!diagnostics ? (
        <p className="mt-4 text-slate-300">Unable to load diagnostics.</p>
      ) : (
        <>
          <div className="mt-4 rounded border border-slate-800 p-4 text-sm text-slate-300">
            <p>Provider: {diagnostics.provider}</p>
            <p>Account Ref: {diagnostics.account_ref}</p>
            <p>Status: {diagnostics.account_status}</p>
            <p>Mode Effective: {diagnostics.mode_effective}</p>
            <p>Health: {diagnostics.health_status}</p>
            <p>Breaker: {diagnostics.breaker_state}</p>
            <p>Scopes: {diagnostics.scopes.join(", ") || "none"}</p>
            <p>Expires: {diagnostics.expires_at ?? "n/a"}</p>
            <p>Last HTTP Status: {diagnostics.last_http_status ?? "n/a"}</p>
            <p>Provider Error: {diagnostics.last_provider_error_code ?? "n/a"}</p>
            <p>Rate Limit Reset: {diagnostics.last_rate_limit_reset_at ?? "n/a"}</p>
            <p>Last Error: {diagnostics.last_error_msg ?? "n/a"}</p>
            <p>Reauth Required: {diagnostics.reauth_required ? "yes" : "no"}</p>
          </div>
          <IntegrationDiagnosticsClient accountId={resolvedParams.accountId} provider={diagnostics.provider} accountRef={diagnostics.account_ref} />
        </>
      )}
    </main>
  );
}

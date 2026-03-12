import { IntegrationsDiagnosticsClient } from "./integrations-diagnostics-client";

export default function IntegrationsDiagnosticsPage() {
  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Integration Diagnostics</h1>
        <p className="page-subtitle">
          Current connector mode, environment readiness, and sanitized integration health signals.
        </p>
      </section>

      <IntegrationsDiagnosticsClient />
    </main>
  );
}

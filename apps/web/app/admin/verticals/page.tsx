import {
  listAdminVerticalPerformance,
  listAdminVerticalRegistry,
  type AdminVerticalPerformanceItem,
  type AdminVerticalRegistryItem,
} from "../../../lib/api";

type PageState = {
  registry: AdminVerticalRegistryItem[];
  performance: AdminVerticalPerformanceItem[];
  notice: string | null;
};

async function getPageState(): Promise<PageState> {
  try {
    const [registry, performance] = await Promise.all([listAdminVerticalRegistry(), listAdminVerticalPerformance()]);
    return { registry, performance, notice: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Global admin access is required for this page.";
    return { registry: [], performance: [], notice: message };
  }
}

export default async function AdminVerticalsPage() {
  const state = await getPageState();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Vertical Registry</h1>
        <p className="page-subtitle">Installed pack versions, checksums, and org-level adoption.</p>
      </section>

      {state.notice ? <section className="surface-card p-4 text-sm text-amber-300">{state.notice}</section> : null}

      <section className="surface-card p-4">
        <h2 className="text-lg font-semibold">Installed Packs</h2>
        <div className="mt-3 overflow-x-auto text-sm">
          <table className="w-full min-w-[680px] table-auto border-collapse">
            <thead>
              <tr className="border-b border-[rgb(var(--border))] text-left text-[rgb(var(--muted-foreground))]">
                <th className="px-2 py-2">Slug</th>
                <th className="px-2 py-2">Version</th>
                <th className="px-2 py-2">Status</th>
                <th className="px-2 py-2">Installed</th>
                <th className="px-2 py-2">Checksum</th>
              </tr>
            </thead>
            <tbody>
              {state.registry.length === 0 ? (
                <tr>
                  <td className="px-2 py-3 text-[rgb(var(--muted-foreground))]" colSpan={5}>
                    No rows.
                  </td>
                </tr>
              ) : null}
              {state.registry.map((row) => (
                <tr className="border-b border-[rgb(var(--border))]" key={`${row.slug}-${row.version}`}>
                  <td className="px-2 py-2">{row.slug}</td>
                  <td className="px-2 py-2">{row.version}</td>
                  <td className="px-2 py-2">{row.status}</td>
                  <td className="px-2 py-2">{new Date(row.installed_at).toLocaleString()}</td>
                  <td className="max-w-[280px] truncate px-2 py-2" title={row.checksum}>{row.checksum}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="surface-card p-4">
        <h2 className="text-lg font-semibold">Vertical Performance</h2>
        <div className="mt-3 overflow-x-auto text-sm">
          <table className="w-full min-w-[760px] table-auto border-collapse">
            <thead>
              <tr className="border-b border-[rgb(var(--border))] text-left text-[rgb(var(--muted-foreground))]">
                <th className="px-2 py-2">Pack</th>
                <th className="px-2 py-2">Orgs</th>
                <th className="px-2 py-2">Funnel</th>
                <th className="px-2 py-2">Revenue</th>
                <th className="px-2 py-2">Automation</th>
                <th className="px-2 py-2">Predictive</th>
              </tr>
            </thead>
            <tbody>
              {state.performance.length === 0 ? (
                <tr>
                  <td className="px-2 py-3 text-[rgb(var(--muted-foreground))]" colSpan={6}>
                    No active org-pack mappings.
                  </td>
                </tr>
              ) : null}
              {state.performance.map((row) => (
                <tr className="border-b border-[rgb(var(--border))]" key={row.pack_slug}>
                  <td className="px-2 py-2">{row.pack_slug}</td>
                  <td className="px-2 py-2">{row.org_count}</td>
                  <td className="px-2 py-2">{row.funnel_events}</td>
                  <td className="px-2 py-2">{row.revenue_events}</td>
                  <td className="px-2 py-2">{row.automation_events}</td>
                  <td className="px-2 py-2">{row.predictive_events}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}


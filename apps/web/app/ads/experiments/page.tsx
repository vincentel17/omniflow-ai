import { apiFetch } from "../../../lib/api";
import { DataTable, EmptyState } from "../../../components/ui/primitives";

type AdExperiment = {
  id: string;
  campaign_id: string;
  name: string;
  status: string;
  success_metric: string;
};

type PageState = {
  experiments: AdExperiment[];
  error: string | null;
};

async function getExperiments(): Promise<PageState> {
  try {
    const experiments = await apiFetch<AdExperiment[]>("/ads/experiments?limit=50&offset=0");
    return { experiments, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load experiments";
    return { experiments: [], error: message };
  }
}

export default async function AdsExperimentsPage() {
  const { experiments, error } = await getExperiments();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Ad Experiments</h1>
        <p className="page-subtitle">A/B experiment lifecycle with approval-gated start and stop actions.</p>
      </section>

      {error ? <section className="surface-card p-4 text-sm text-amber-300">API note: {error}</section> : null}

      {experiments.length === 0 ? (
        <EmptyState title="No experiments" description="Create an experiment from a campaign to track variant performance." />
      ) : (
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Name</th>
                <th>Campaign</th>
                <th>Status</th>
                <th>Success Metric</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((experiment) => (
                <tr key={experiment.id}>
                  <td>{experiment.name}</td>
                  <td className="font-mono text-xs">{experiment.campaign_id}</td>
                  <td>{experiment.status}</td>
                  <td>{experiment.success_metric}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}

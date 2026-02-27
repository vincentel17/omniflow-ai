import { apiFetch } from "../../../lib/api";
import { DataTable, EmptyState } from "../../../components/ui/primitives";

type AdCampaign = {
  id: string;
  name: string;
  provider: string;
  objective: string;
  status: string;
  daily_budget_usd: number | null;
};

async function getCampaigns(): Promise<AdCampaign[]> {
  try {
    return await apiFetch<AdCampaign[]>("/ads/campaigns?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function AdsCampaignsPage() {
  const campaigns = await getCampaigns();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Ad Campaigns</h1>
        <p className="page-subtitle">Draft, activation, and budget status for guarded campaign rollout.</p>
      </section>

      {campaigns.length === 0 ? (
        <EmptyState title="No ad campaigns" description="Create campaigns via the ads API to validate end-to-end guarded flow." />
      ) : (
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Name</th>
                <th>Provider</th>
                <th>Objective</th>
                <th>Status</th>
                <th>Daily Budget</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={campaign.id}>
                  <td>{campaign.name}</td>
                  <td>{campaign.provider}</td>
                  <td>{campaign.objective}</td>
                  <td>{campaign.status}</td>
                  <td>{campaign.daily_budget_usd ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}

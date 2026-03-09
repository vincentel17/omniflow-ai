import Link from "next/link";

import { apiFetch } from "../../../lib/api";
import { DataTable, EmptyState } from "../../../components/ui/primitives";
import { requireAuthSession } from "../../../lib/server-auth";
import { CreativeActions } from "./creative-actions";

type AdCreative = {
  id: string;
  campaign_id: string;
  name: string;
  format: string;
  status: string;
};

type PageState = {
  creatives: AdCreative[];
  error: string | null;
};

async function getCreatives(): Promise<PageState> {
  try {
    const creatives = await apiFetch<AdCreative[]>("/ads/creatives?limit=50&offset=0");
    return { creatives, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load creatives";
    return { creatives: [], error: message };
  }
}

export default async function AdsCreativesPage() {
  await requireAuthSession();
  const { creatives, error } = await getCreatives();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Ad Creatives</h1>
        <p className="page-subtitle">Tracked-link-bound creatives and approval readiness.</p>
      </section>

      {error ? <section className="surface-card p-4 text-sm text-amber-300">API note: {error}</section> : null}

      {creatives.length === 0 ? (
        <EmptyState title="No creatives" description="Creatives will appear after campaigns attach approved creative variants." />
      ) : (
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Name</th>
                <th>Campaign</th>
                <th>Format</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {creatives.map((creative) => (
                <tr key={creative.id}>
                  <td>{creative.name}</td>
                  <td className="font-mono text-xs">
                    <Link className="underline-offset-4 hover:underline" href={`/ads/campaigns/${creative.campaign_id}`}>{creative.campaign_id}</Link>
                  </td>
                  <td>{creative.format}</td>
                  <td>{creative.status}</td>
                  <td>
                    <CreativeActions creativeId={creative.id} status={creative.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}

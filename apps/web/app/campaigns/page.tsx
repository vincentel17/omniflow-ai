import { apiFetch } from "../../lib/api";
import { CampaignPlanner } from "./planner";

type Campaign = {
  id: string;
  week_start_date: string;
  status: string;
  vertical_pack_slug: string;
  created_at: string;
};

async function getCampaigns(): Promise<Campaign[]> {
  try {
    return await apiFetch<Campaign[]>("/campaigns?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function CampaignsPage() {
  const campaigns = await getCampaigns();
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Campaign Planner</h1>
      <p className="mt-2 text-slate-300">Generate weekly plan JSON and create content items from it.</p>
      <CampaignPlanner campaigns={campaigns} />
    </main>
  );
}

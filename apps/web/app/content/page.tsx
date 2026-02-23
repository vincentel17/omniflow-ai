import { apiFetch } from "../../lib/api";
import { ContentQueue } from "./queue";

type ContentItem = {
  id: string;
  campaign_plan_id: string;
  channel: string;
  status: string;
  risk_tier: string;
  policy_warnings_json: string[];
  created_at: string;
};

async function getContent(): Promise<ContentItem[]> {
  return apiFetch<ContentItem[]>("/content?limit=50&offset=0");
}

export default async function ContentPage() {
  const items = await getContent();
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Content Queue</h1>
      <p className="mt-2 text-slate-300">Approve and schedule generated content items for publishing.</p>
      <ContentQueue items={items} />
    </main>
  );
}

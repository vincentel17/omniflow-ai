import { apiFetch } from "../../../lib/api";

type ContentResponse = {
  group_by: string;
  content_items_by_status: Record<string, number>;
  publish_success_rate: number;
  clicks_by_content: Array<{ content_id: string; clicks: number }>;
  leads_by_content: Array<{ content_id: string; leads: number }>;
};

export default async function AnalyticsContentPage() {
  const data = await apiFetch<ContentResponse>("/analytics/content?group_by=day");

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Content Analytics</h1>
      <p className="mt-2 text-slate-400">Publish outcomes and attributed clicks/leads by content item.</p>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <p className="text-sm text-slate-300">Publish success rate: {data.publish_success_rate}%</p>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(data.content_items_by_status, null, 2)}
        </pre>
      </section>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Clicks by Content</h2>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(data.clicks_by_content, null, 2)}
        </pre>
      </section>
      <section className="mt-6 rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Leads by Content</h2>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(data.leads_by_content, null, 2)}
        </pre>
      </section>
    </main>
  );
}


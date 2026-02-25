import { apiFetch } from "../../lib/api";
import { SEOConsole } from "./seo-console";

type WorkItem = {
  id: string;
  type: string;
  status: string;
  target_keyword: string;
  url_slug: string;
  rendered_markdown: string | null;
};

export default async function SEOPage() {
  const workItems = await apiFetch<WorkItem[]>("/seo/work-items?limit=50&offset=0");
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">SEO Engine</h1>
      <p className="mt-2 text-slate-400">Generate plans, create work items, draft content, and approve.</p>
      <SEOConsole initialWorkItems={workItems} />
    </main>
  );
}


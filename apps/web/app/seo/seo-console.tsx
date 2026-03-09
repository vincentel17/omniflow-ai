"use client";

import { useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";

type WorkItem = {
  id: string;
  type: string;
  status: string;
  target_keyword: string;
  url_slug: string;
  rendered_markdown: string | null;
};

type Props = {
  initialWorkItems: WorkItem[];
};

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json"
  };
}

export function SEOConsole({ initialWorkItems }: Props) {
  const [workItems, setWorkItems] = useState<WorkItem[]>(initialWorkItems);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  async function refresh() {
    setPendingAction("refresh");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/seo/work-items?limit=50&offset=0`, {
        headers: headers(),
        credentials: "include",
        cache: "no-store"
      });
      if (!response.ok) {
        setStatus(`Refresh failed (${response.status})`);
        return;
      }
      setWorkItems((await response.json()) as WorkItem[]);
    } catch {
      setStatus("Refresh failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function generatePlan() {
    setPendingAction("plan");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/seo/plan`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({ target_locations: ["seattle"] })
      });
      if (!response.ok) {
        setStatus(`Plan failed (${response.status})`);
        return;
      }
      const payload = (await response.json()) as { service_pages: Array<{ keyword: string; slug: string }> };
      const first = payload.service_pages[0];
      if (!first) {
        setStatus("Plan returned no service pages.");
        return;
      }
      const create = await fetch(`${getApiBaseUrl()}/seo/work-items`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({
          type: "service_page",
          target_keyword: first.keyword,
          target_location: "Seattle",
          url_slug: first.slug,
          content_json: { title: first.keyword }
        })
      });
      if (!create.ok) {
        setStatus(`Create failed (${create.status})`);
        return;
      }
      setStatus("SEO plan generated and work item created.");
      await refresh();
    } catch {
      setStatus("Plan failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function generateContent(id: string) {
    setPendingAction(`generate-${id}`);
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/seo/work-items/${id}/generate`, {
        method: "POST",
        headers: headers(),
        credentials: "include"
      });
      if (!response.ok) {
        setStatus(`Generate failed (${response.status})`);
        return;
      }
      setStatus("SEO content generated.");
      await refresh();
    } catch {
      setStatus("Generate failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function approve(id: string) {
    setPendingAction(`approve-${id}`);
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/seo/work-items/${id}/approve`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({ status: "approved" })
      });
      if (!response.ok) {
        setStatus(`Approve failed (${response.status})`);
        return;
      }
      setStatus("SEO work item approved.");
      await refresh();
    } catch {
      setStatus("Approve failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="mt-6 space-y-6">
      <section className="rounded border border-slate-800 p-4">
        <button
          className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900"
          data-testid="tour-seo-create-task"
          disabled={pendingAction !== null}
          onClick={generatePlan}
          type="button"
        >
          {pendingAction === "plan" ? "Generating..." : "Generate SEO Plan"}
        </button>
        <button
          className="ml-2 rounded bg-slate-700 px-3 py-1 text-sm"
          data-testid="seo-refresh"
          disabled={pendingAction !== null}
          onClick={refresh}
          type="button"
        >
          {pendingAction === "refresh" ? "Refreshing..." : "Refresh"}
        </button>
      </section>
      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Work Items</h2>
        <ul className="mt-3 space-y-2">
          {workItems.map((item) => (
            <li className="rounded border border-slate-700 p-3" key={item.id}>
              <p className="font-medium">
                {item.type} | {item.target_keyword}
              </p>
              <p className="text-sm text-slate-400">{item.status}</p>
              <div className="mt-2 flex gap-2">
                <button
                  className="rounded bg-slate-700 px-3 py-1 text-sm"
                  data-testid={`seo-generate-${item.id}`}
                  disabled={pendingAction !== null}
                  onClick={() => generateContent(item.id)}
                  type="button"
                >
                  {pendingAction === `generate-${item.id}` ? "Generating..." : "Generate"}
                </button>
                <button
                  className="rounded bg-slate-700 px-3 py-1 text-sm"
                  data-testid={`seo-approve-${item.id}`}
                  disabled={pendingAction !== null}
                  onClick={() => approve(item.id)}
                  type="button"
                >
                  {pendingAction === `approve-${item.id}` ? "Approving..." : "Approve"}
                </button>
                <a
                  className="rounded bg-slate-700 px-3 py-1 text-sm"
                  href={`${getApiBaseUrl()}/seo/work-items/${item.id}/export`}
                  rel="noreferrer"
                  target="_blank"
                >
                  Export Markdown
                </a>
              </div>
            </li>
          ))}
        </ul>
      </section>
      {status ? <p className="text-sm text-slate-300" data-testid="seo-status-message">{status}</p> : null}
    </div>
  );
}

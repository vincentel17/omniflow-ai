"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type CMAReport = {
  id: string;
  created_at: string;
  narrative_text: string | null;
  pricing_json: Record<string, unknown>;
  policy_warnings_json: string[];
};

type Props = {
  initialReports: CMAReport[];
};

function headers(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role
  };
}

export function CMAConsole({ initialReports }: Props) {
  const [reports, setReports] = useState<CMAReport[]>(initialReports);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`${getApiBaseUrl()}/re/cma/reports?limit=50&offset=0`, { headers: headers(), cache: "no-store" });
    if (!response.ok) {
      setStatus(`Refresh failed (${response.status})`);
      return;
    }
    setReports((await response.json()) as CMAReport[]);
  }

  async function createReport() {
    const response = await fetch(`${getApiBaseUrl()}/re/cma/reports`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        subject_property_json: { address: "500 Sample St", beds: 3, baths: 2, sqft: 1800 }
      })
    });
    if (!response.ok) {
      setStatus(`Create failed (${response.status})`);
      return;
    }
    setStatus("CMA report created.");
    await refresh();
  }

  async function importComps(reportId: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/cma/reports/${reportId}/comps/import`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        comparables: [
          { address: "1 Comp St", status: "sold", sold_price: 420000, sqft: 1900 },
          { address: "2 Comp St", status: "sold", sold_price: 410000, sqft: 1850 },
          { address: "3 Comp St", status: "active", list_price: 430000, sqft: 2000 }
        ]
      })
    });
    if (!response.ok) {
      setStatus(`Import failed (${response.status})`);
      return;
    }
    setStatus("Comps imported.");
  }

  async function generate(reportId: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/cma/reports/${reportId}/generate`, {
      method: "POST",
      headers: headers()
    });
    if (!response.ok) {
      setStatus(`Generate failed (${response.status})`);
      return;
    }
    setStatus("CMA generated.");
    await refresh();
  }

  function exportReport(reportId: string) {
    window.open(`${getApiBaseUrl()}/re/cma/reports/${reportId}/export`, "_blank");
    setStatus("Opened export.");
  }

  return (
    <div className="mt-6 grid gap-6">
      <section className="rounded border border-slate-800 p-4">
        <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" type="button" onClick={createReport}>
          Create CMA Report
        </button>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Reports</h2>
        <ul className="mt-3 space-y-2">
          {reports.map((report) => (
            <li className="rounded border border-slate-700 p-3" key={report.id}>
              <p className="font-medium">Report {report.id}</p>
              <p className="text-sm text-slate-400">
                Suggested price: {String(report.pricing_json.suggested_price ?? "n/a")}
              </p>
              <p className="text-sm text-amber-300">
                {report.policy_warnings_json.length > 0 ? `Policy warnings: ${report.policy_warnings_json.join(", ")}` : "Disclaimers validated"}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => importComps(report.id)}>
                  Import Comps
                </button>
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => generate(report.id)}>
                  Generate
                </button>
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => exportReport(report.id)}>
                  Export
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </div>
  );
}


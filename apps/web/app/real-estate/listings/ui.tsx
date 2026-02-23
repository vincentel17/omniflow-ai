"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type ListingPackage = {
  id: string;
  status: string;
  risk_tier: string;
  policy_warnings_json: string[];
  created_at: string;
};

type Props = {
  initialPackages: ListingPackage[];
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

export function ListingsConsole({ initialPackages }: Props) {
  const [packages, setPackages] = useState<ListingPackage[]>(initialPackages);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`${getApiBaseUrl()}/re/listings/packages?limit=50&offset=0`, { headers: headers(), cache: "no-store" });
    if (!response.ok) {
      setStatus(`Refresh failed (${response.status})`);
      return;
    }
    setPackages((await response.json()) as ListingPackage[]);
  }

  async function createPackage() {
    const response = await fetch(`${getApiBaseUrl()}/re/listings/packages`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        property_address_json: { address: "200 Listing Ln", beds: 4, baths: 3, sqft: 2400 },
        key_features_json: ["Updated kitchen", "Large lot", "Natural light"]
      })
    });
    if (!response.ok) {
      setStatus(`Create failed (${response.status})`);
      return;
    }
    setStatus("Listing package created.");
    await refresh();
  }

  async function generatePackage(id: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/listings/packages/${id}/generate`, { method: "POST", headers: headers() });
    if (!response.ok) {
      setStatus(`Generate failed (${response.status})`);
      return;
    }
    setStatus("Listing package generated.");
    await refresh();
  }

  async function approvePackage(id: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/listings/packages/${id}/approve`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ status: "approved", notes: "Approved from listing ops UI" })
    });
    if (!response.ok) {
      setStatus(`Approve failed (${response.status})`);
      return;
    }
    setStatus("Listing package approved.");
    await refresh();
  }

  async function pushToContent(id: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/listings/packages/${id}/push-to-content-queue`, { method: "POST", headers: headers() });
    if (!response.ok) {
      setStatus(`Push failed (${response.status})`);
      return;
    }
    setStatus("Pushed to content queue.");
  }

  return (
    <div className="mt-6 grid gap-6">
      <section className="rounded border border-slate-800 p-4">
        <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" type="button" onClick={createPackage}>
          Create Listing Package
        </button>
      </section>
      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Packages</h2>
        <ul className="mt-3 space-y-2">
          {packages.map((item) => (
            <li className="rounded border border-slate-700 p-3" key={item.id}>
              <p className="font-medium">
                {item.status} | {item.risk_tier}
              </p>
              <p className="text-sm text-amber-300">
                {item.policy_warnings_json.length > 0 ? `Policy warnings: ${item.policy_warnings_json.join(", ")}` : "Disclaimers validated"}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => generatePackage(item.id)}>
                  Generate
                </button>
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => approvePackage(item.id)}>
                  Approve
                </button>
                <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => pushToContent(item.id)}>
                  Push to Content Queue
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


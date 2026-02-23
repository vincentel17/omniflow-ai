"use client";

import Link from "next/link";
import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Deal = {
  id: string;
  deal_type: string;
  status: string;
  pipeline_stage: string;
  primary_contact_name: string | null;
  created_at: string;
};

type Props = {
  initialDeals: Deal[];
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

export function DealsConsole({ initialDeals }: Props) {
  const [deals, setDeals] = useState<Deal[]>(initialDeals);
  const [status, setStatus] = useState<string | null>(null);
  const [dealType, setDealType] = useState("buyer");
  const [stage, setStage] = useState("Lead");
  const [address, setAddress] = useState("123 Main St");
  const [contactName, setContactName] = useState("Client Name");

  async function refresh() {
    const response = await fetch(`${getApiBaseUrl()}/re/deals?limit=50&offset=0`, { headers: headers(), cache: "no-store" });
    if (!response.ok) {
      setStatus(`Refresh failed (${response.status})`);
      return;
    }
    setDeals((await response.json()) as Deal[]);
  }

  async function createDeal() {
    const response = await fetch(`${getApiBaseUrl()}/re/deals`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        deal_type: dealType,
        pipeline_stage: stage,
        primary_contact_name: contactName,
        property_address_json: { address },
        important_dates_json: {}
      })
    });
    if (!response.ok) {
      setStatus(`Create failed (${response.status})`);
      return;
    }
    setStatus("Deal created.");
    await refresh();
  }

  return (
    <div className="mt-6 grid gap-6">
      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Create Deal</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <input className="rounded bg-slate-900 p-2 text-sm" value={dealType} onChange={(e) => setDealType(e.target.value)} />
          <input className="rounded bg-slate-900 p-2 text-sm" value={stage} onChange={(e) => setStage(e.target.value)} />
          <input className="rounded bg-slate-900 p-2 text-sm" value={address} onChange={(e) => setAddress(e.target.value)} />
          <input className="rounded bg-slate-900 p-2 text-sm" value={contactName} onChange={(e) => setContactName(e.target.value)} />
        </div>
        <button className="mt-3 rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" type="button" onClick={createDeal}>
          Create
        </button>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Deals</h2>
        <ul className="mt-3 space-y-2">
          {deals.map((deal) => (
            <li key={deal.id} className="rounded border border-slate-700 p-3">
              <p className="font-medium">
                {deal.deal_type} | {deal.pipeline_stage} | {deal.status}
              </p>
              <p className="text-sm text-slate-400">{deal.primary_contact_name ?? "No contact"} </p>
              <Link className="mt-2 inline-block text-sm underline" href={`/real-estate/deals/${deal.id}`}>
                Open deal
              </Link>
            </li>
          ))}
        </ul>
      </section>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </div>
  );
}


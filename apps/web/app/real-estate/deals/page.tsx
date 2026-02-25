import { apiFetch } from "../../../lib/api";
import { DealsConsole } from "./deals-console";

type Deal = {
  id: string;
  deal_type: string;
  status: string;
  pipeline_stage: string;
  primary_contact_name: string | null;
  created_at: string;
};

export default async function RealEstateDealsPage() {
  const deals = await apiFetch<Deal[]>("/re/deals?limit=50&offset=0");
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Real Estate Deals</h1>
      <p className="mt-2 text-slate-400">Create and manage transactions with stage, checklist, docs, and communication logs.</p>
      <DealsConsole initialDeals={deals} />
    </main>
  );
}



import { apiFetch } from "../../../lib/api";
import { ListingsConsole } from "./ui";

type ListingPackage = {
  id: string;
  status: string;
  risk_tier: string;
  policy_warnings_json: string[];
  created_at: string;
};

export default async function RealEstateListingsPage() {
  const packages = await apiFetch<ListingPackage[]>("/re/listings/packages?limit=50&offset=0");
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Listing Ops</h1>
      <p className="mt-2 text-slate-400">Generate listing descriptions, open house plans, and push social packs into the content queue.</p>
      <ListingsConsole initialPackages={packages} />
    </main>
  );
}



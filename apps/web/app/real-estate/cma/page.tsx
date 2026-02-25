import { apiFetch } from "../../../lib/api";
import { CMAConsole } from "./ui";

type CMAReport = {
  id: string;
  created_at: string;
  narrative_text: string | null;
  pricing_json: Record<string, unknown>;
  policy_warnings_json: string[];
};

export default async function RealEstateCMAPage() {
  const reports = await apiFetch<CMAReport[]>("/re/cma/reports?limit=50&offset=0");
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">CMA Builder</h1>
      <p className="mt-2 text-slate-400">Create reports from manual comps and export print-ready HTML.</p>
      <CMAConsole initialReports={reports} />
    </main>
  );
}



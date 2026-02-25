import { apiFetch } from "../../../../lib/api";
import { DealDetailConsole } from "./ui";

type Deal = {
  id: string;
  deal_type: string;
  status: string;
  pipeline_stage: string;
  property_address_json: Record<string, unknown>;
  important_dates_json: Record<string, unknown>;
};

type ChecklistItem = {
  id: string;
  title: string;
  status: string;
  due_at: string | null;
};

type DocumentRequest = {
  id: string;
  doc_type: string;
  requested_from: string;
  status: string;
};

type Communication = {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body_text: string;
};

export default async function DealDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [deal, checklistItems, documents, communications] = await Promise.all([
    apiFetch<Deal>(`/re/deals/${id}`),
    apiFetch<ChecklistItem[]>(`/re/deals/${id}/checklist-items?limit=100&offset=0`),
    apiFetch<DocumentRequest[]>(`/re/deals/${id}/documents?limit=100&offset=0`),
    apiFetch<Communication[]>(`/re/deals/${id}/communications?limit=100&offset=0`)
  ]);

  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Deal Detail</h1>
      <p className="mt-2 text-slate-400">
        {deal.deal_type} | {deal.pipeline_stage} | {deal.status}
      </p>
      <DealDetailConsole dealId={deal.id} initialChecklist={checklistItems} initialDocuments={documents} initialCommunications={communications} />
    </main>
  );
}

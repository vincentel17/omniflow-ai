import { apiFetch } from "../../lib/api";
import { EmptyState } from "../../components/ui/primitives";
import { requireAuthSession } from "../../lib/server-auth";
import { ApprovalsConsole } from "./approvals-console";

type Approval = {
  id: string;
  entity_type: string;
  entity_id: string;
  status: string;
  created_at: string;
};

async function getApprovals(): Promise<Approval[]> {
  try {
    return await apiFetch<Approval[]>("/approvals?limit=50&offset=0");
  } catch {
    return [];
  }
}

export default async function ApprovalsPage() {
  await requireAuthSession();
  const approvals = await getApprovals();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Approvals</h1>
        <p className="page-subtitle">Review queue for guarded actions across workflows, ads, and integrations.</p>
      </section>

      {approvals.length === 0 ? (
        <EmptyState title="No pending approvals" description="Approval requests will appear here when high-risk actions are queued." />
      ) : (
        <ApprovalsConsole initialApprovals={approvals} />
      )}
    </main>
  );
}

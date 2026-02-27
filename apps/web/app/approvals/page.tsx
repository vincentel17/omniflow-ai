import { apiFetch } from "../../lib/api";
import { DataTable, EmptyState } from "../../components/ui/primitives";

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
        <div className="surface-card p-4">
          <DataTable>
            <thead>
              <tr>
                <th>Approval</th>
                <th>Entity</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((item) => (
                <tr key={item.id}>
                  <td className="font-mono text-xs">{item.id}</td>
                  <td>{item.entity_type}:{" "}<span className="font-mono text-xs">{item.entity_id}</span></td>
                  <td>{item.status}</td>
                  <td>{item.created_at}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </main>
  );
}

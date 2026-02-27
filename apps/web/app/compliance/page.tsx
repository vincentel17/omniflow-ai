import { Badge, Card, CardContent, CardHeader, CardTitle, DataTable, EmptyState } from "../../components/ui/primitives";
import {
  getComplianceEvidenceBundle,
  getComplianceMode,
  getComplianceRbacMatrix,
  getComplianceRetentionPolicies,
  listComplianceDsarRequests,
} from "../../lib/api";

type DashboardData = {
  mode: string;
  retentionCount: number;
  pendingDsar: number;
  rbacRoleCount: number;
  recentDsar: { id: string; status: string; request_type: string; requested_at: string }[];
  evidenceSections: string[];
};

async function getDashboardData(): Promise<DashboardData> {
  try {
    const [mode, retention, dsar, rbac] = await Promise.all([
      getComplianceMode(),
      getComplianceRetentionPolicies(),
      listComplianceDsarRequests(20, 0),
      getComplianceRbacMatrix(),
    ]);

    let evidenceSections: string[] = [];
    try {
      const now = new Date();
      const from = new Date(now);
      from.setDate(now.getDate() - 7);
      const evidence = await getComplianceEvidenceBundle(from.toISOString().slice(0, 10), now.toISOString().slice(0, 10), false);
      evidenceSections = Object.keys(evidence.bundle_json ?? {});
    } catch {
      evidenceSections = [];
    }

    return {
      mode: mode.compliance_mode,
      retentionCount: retention.length,
      pendingDsar: dsar.filter((row) => row.status === "requested" || row.status === "in_progress").length,
      rbacRoleCount: Object.keys(rbac.roles ?? {}).length,
      recentDsar: dsar.slice(0, 8),
      evidenceSections,
    };
  } catch {
    return {
      mode: "none",
      retentionCount: 0,
      pendingDsar: 0,
      rbacRoleCount: 0,
      recentDsar: [],
      evidenceSections: [],
    };
  }
}

export default async function CompliancePage() {
  const data = await getDashboardData();

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card overflow-hidden">
        <div className="bg-gradient-to-r from-[rgb(var(--primary-deep))]/25 via-[rgb(var(--accent-teal))]/20 to-[rgb(var(--accent-gold))]/20 p-6">
          <h1 className="page-title">Compliance Dashboard</h1>
          <p className="page-subtitle">Data governance controls, DSAR handling, retention posture, and audit evidence in one place.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone={data.mode === "none" ? "warn" : "info"}>Mode: {data.mode}</Badge>
            <Badge tone="neutral">Admin only</Badge>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Retention Policies</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.retentionCount}</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Configured entity retention rules</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pending DSAR</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.pendingDsar}</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Requests awaiting completion</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>RBAC Roles</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.rbacRoleCount}</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Roles included in permission matrix</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Evidence Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.evidenceSections.length}</p>
            <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Sections in last 7-day export</p>
          </CardContent>
        </Card>
      </section>

      <section className="surface-card p-4">
        <h2 className="mb-3 text-lg font-semibold">Recent DSAR Requests</h2>
        {data.recentDsar.length === 0 ? (
          <EmptyState
            title="No DSAR requests"
            description="Create a DSAR request from compliance APIs to validate access/delete workflows."
          />
        ) : (
          <div className="overflow-x-auto">
            <DataTable>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Requested</th>
                </tr>
              </thead>
              <tbody>
                {data.recentDsar.map((row) => (
                  <tr key={row.id}>
                    <td className="font-mono text-xs">{row.id.slice(0, 8)}</td>
                    <td>{row.request_type}</td>
                    <td>
                      <Badge tone={row.status === "completed" ? "success" : row.status === "rejected" ? "danger" : "warn"}>{row.status}</Badge>
                    </td>
                    <td>{new Date(row.requested_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        )}
      </section>
    </main>
  );
}

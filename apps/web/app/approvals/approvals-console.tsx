"use client";

import { useMemo, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

type Approval = {
  id: string;
  entity_type: string;
  entity_id: string;
  status: string;
  created_at: string;
};

type Props = {
  initialApprovals: Approval[];
};

function headers(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role,
  };
}

export function ApprovalsConsole({ initialApprovals }: Props) {
  const [approvals, setApprovals] = useState(initialApprovals);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const openApprovals = useMemo(() => approvals.filter((item) => item.status === "pending"), [approvals]);

  async function decideApproval(approvalId: string, decision: "approve" | "reject") {
    setPendingId(approvalId);
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/approvals/${approvalId}/${decision}`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
        body: JSON.stringify({
          notes: decision === "approve" ? "Approved from approvals queue" : "Rejected from approvals queue",
        }),
      });
      if (!response.ok) {
        setStatus(`${decision === "approve" ? "Approve" : "Reject"} failed (${response.status}).`);
        return;
      }
      const updated = (await response.json()) as Approval;
      setApprovals((current) => current.map((item) => (item.id === approvalId ? updated : item)));
      setStatus(decision === "approve" ? "Approval granted." : "Approval rejected.");
    } catch {
      setStatus(`${decision === "approve" ? "Approve" : "Reject"} failed (network error).`);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="surface-card p-4">
      {status ? <p className="mb-3 text-sm text-slate-300">{status}</p> : null}
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="px-3 py-2">Approval</th>
            <th className="px-3 py-2">Entity</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Created</th>
            <th className="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {approvals.map((item) => {
            const isPending = item.status === "pending";
            const busy = pendingId === item.id;
            return (
              <tr className="border-b border-[var(--border)] align-top" key={item.id}>
                <td className="px-3 py-3 font-mono text-xs">{item.id}</td>
                <td className="px-3 py-3">
                  {item.entity_type}: <span className="font-mono text-xs">{item.entity_id}</span>
                </td>
                <td className="px-3 py-3">{item.status}</td>
                <td className="px-3 py-3">{item.created_at}</td>
                <td className="px-3 py-3">
                  <div className="flex gap-2">
                    <button
                      className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900 disabled:opacity-50"
                      data-testid={openApprovals[0]?.id === item.id ? "tour-approvals-approve" : `approve-${item.id}`}
                      disabled={!isPending || busy}
                      onClick={() => decideApproval(item.id, "approve")}
                      type="button"
                    >
                      {busy ? "Working..." : "Approve"}
                    </button>
                    <button
                      className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-100 disabled:opacity-50"
                      data-testid={openApprovals[0]?.id === item.id ? "tour-approvals-reject" : `reject-${item.id}`}
                      disabled={!isPending || busy}
                      onClick={() => decideApproval(item.id, "reject")}
                      type="button"
                    >
                      {busy ? "Working..." : "Reject"}
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { ApiError } from "../../../../../lib/api";
import { approveApproval, executeAgentRun, rejectApproval } from "../../../../../lib/api";
import { Button, ButtonGhost } from "../../../../../components/ui/primitives";

function renderError(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "message" in error && typeof (error as ApiError).message === "string") {
    const typedError = error as ApiError;
    return typedError.requestId ? `${typedError.message} [request_id=${typedError.requestId}]` : typedError.message;
  }
  return fallback;
}

type AgentRunActionsProps = {
  runId: string;
  approvalId?: string;
};

export function AgentRunActions({ runId, approvalId }: AgentRunActionsProps) {
  const router = useRouter();
  const [pending, setPending] = useState<"execute" | "approve" | "reject" | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function executeRun() {
    setPending("execute");
    setStatus(null);
    try {
      await executeAgentRun(runId);
      setStatus("Run execution requested.");
      router.refresh();
    } catch (error) {
      setStatus(renderError(error, "Execute run failed."));
    } finally {
      setPending(null);
    }
  }

  async function approve() {
    if (!approvalId) {
      return;
    }
    setPending("approve");
    setStatus(null);
    try {
      await approveApproval(approvalId);
      setStatus("Approval accepted.");
      router.refresh();
    } catch (error) {
      setStatus(renderError(error, "Approve failed."));
    } finally {
      setPending(null);
    }
  }

  async function reject() {
    if (!approvalId) {
      return;
    }
    setPending("reject");
    setStatus(null);
    try {
      await rejectApproval(approvalId);
      setStatus("Approval rejected.");
      router.refresh();
    } catch (error) {
      setStatus(renderError(error, "Reject failed."));
    } finally {
      setPending(null);
    }
  }

  if (approvalId) {
    return (
      <div className="space-y-2">
        <div className="flex gap-2">
          <Button data-testid={`agent-approval-approve-${approvalId}`} disabled={pending !== null} onClick={() => void approve()} type="button">
            {pending === "approve" ? "Approving..." : "Approve"}
          </Button>
          <ButtonGhost data-testid={`agent-approval-reject-${approvalId}`} disabled={pending !== null} onClick={() => void reject()} type="button">
            {pending === "reject" ? "Rejecting..." : "Reject"}
          </ButtonGhost>
        </div>
        {status ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{status}</p> : null}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Button data-testid="agent-run-execute" disabled={pending !== null} onClick={() => void executeRun()} type="button">
        {pending === "execute" ? "Executing..." : "Execute Run"}
      </Button>
      {status ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{status}</p> : null}
    </div>
  );
}

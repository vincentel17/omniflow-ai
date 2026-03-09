"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch, type ApiError } from "../../../lib/api";

type Props = {
  workflowId: string;
  enabled: boolean;
};

export function WorkflowActions({ workflowId, enabled }: Props) {
  const router = useRouter();
  const [pending, setPending] = useState<"toggle" | "test" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function onToggle(): Promise<void> {
    setPending("toggle");
    setMessage(null);
    try {
      await apiFetch(`/workflows/${workflowId}`, {
        method: "PATCH",
        body: { enabled: !enabled },
      });
      setMessage("Workflow updated.");
      router.refresh();
    } catch (error) {
      if (isApiError(error)) {
        setMessage(error.message);
      } else {
        setMessage("Toggle failed (network error).");
      }
    } finally {
      setPending(null);
    }
  }

  async function onDryRun(): Promise<void> {
    setPending("test");
    setMessage(null);
    try {
      const payload = await apiFetch<{ matched: boolean; actions?: unknown[] }>(`/workflows/${workflowId}/test`, {
        method: "POST",
        body: {
          event_type: "WORKFLOW_DRY_RUN",
          channel: "workflow",
          payload_json: {},
          risk_tier: 0,
        },
      });
      const actionsCount = Array.isArray(payload.actions) ? payload.actions.length : 0;
      setMessage(payload.matched ? `Dry-run matched (${actionsCount} action(s)).` : "Dry-run did not match.");
    } catch (error) {
      if (isApiError(error)) {
        setMessage(error.message);
      } else {
        setMessage("Dry-run failed (network error).");
      }
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-secondary btn-sm" data-testid={`workflow-toggle-${workflowId}`} disabled={pending !== null} onClick={() => void onToggle()} type="button">
          {pending === "toggle" ? "Saving..." : enabled ? "Disable" : "Enable"}
        </button>
        <button className="btn btn-secondary btn-sm" data-testid={`workflow-dryrun-${workflowId}`} disabled={pending !== null} onClick={() => void onDryRun()} type="button">
          {pending === "test" ? "Testing..." : "Dry Run"}
        </button>
      </div>
      {message ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{message}</p> : null}
    </div>
  );
}

function isApiError(error: unknown): error is ApiError {
  return typeof error === "object" && error !== null && "status" in error && "message" in error;
}

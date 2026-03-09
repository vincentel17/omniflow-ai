"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Props = {
  workflowId: string;
  enabled: boolean;
};

function contextHeaders(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role,
  };
}

export function WorkflowActions({ workflowId, enabled }: Props) {
  const [pending, setPending] = useState<"toggle" | "test" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function onToggle(): Promise<void> {
    setPending("toggle");
    setMessage(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/workflows/${workflowId}`, {
        method: "PATCH",
        headers: contextHeaders(),
        credentials: "include",
        body: JSON.stringify({ enabled: !enabled }),
      });
      if (!response.ok) {
        setMessage(`Toggle failed (${response.status})`);
        return;
      }
      setMessage("Workflow updated. Refreshing...");
      window.location.reload();
    } catch {
      setMessage("Toggle failed (network error).");
    } finally {
      setPending(null);
    }
  }

  async function onDryRun(): Promise<void> {
    setPending("test");
    setMessage(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/workflows/${workflowId}/test`, {
        method: "POST",
        headers: contextHeaders(),
        credentials: "include",
        body: JSON.stringify({
          event_type: "WORKFLOW_DRY_RUN",
          channel: "workflow",
          payload_json: {},
          risk_tier: 0,
        }),
      });
      if (!response.ok) {
        setMessage(`Dry-run failed (${response.status})`);
        return;
      }
      const payload = (await response.json()) as { matched: boolean; actions?: unknown[] };
      const actionsCount = Array.isArray(payload.actions) ? payload.actions.length : 0;
      setMessage(payload.matched ? `Dry-run matched (${actionsCount} action(s)).` : "Dry-run did not match.");
    } catch {
      setMessage("Dry-run failed (network error).");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-secondary btn-sm" disabled={pending !== null} onClick={() => void onToggle()} type="button">
          {pending === "toggle" ? "Saving..." : enabled ? "Disable" : "Enable"}
        </button>
        <button className="btn btn-secondary btn-sm" disabled={pending !== null} onClick={() => void onDryRun()} type="button">
          {pending === "test" ? "Testing..." : "Dry Run"}
        </button>
      </div>
      {message ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{message}</p> : null}
    </div>
  );
}


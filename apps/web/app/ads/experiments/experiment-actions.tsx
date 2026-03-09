"use client";

import { useState } from "react";

import { getApiBaseUrl } from "../../../lib/dev-context";

type Props = {
  experimentId: string;
  status: string;
};

type ActionType = "start" | "stop" | null;

function actionForStatus(status: string): ActionType {
  const normalized = status.toLowerCase();
  if (normalized === "draft") {
    return "start";
  }
  if (normalized === "running") {
    return "stop";
  }
  return null;
}

export function ExperimentActions({ experimentId, status }: Props) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const action = actionForStatus(status);

  async function onExecute(): Promise<void> {
    if (!action || pending) {
      return;
    }
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/ads/experiments/${experimentId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });
      if (!response.ok) {
        setMessage(`Action failed (${response.status})`);
        return;
      }
      setMessage("Updated. Refreshing...");
      window.location.reload();
    } catch {
      setMessage("Action failed (network error).");
    } finally {
      setPending(false);
    }
  }

  if (!action) {
    return <span className="text-xs text-[rgb(var(--muted-foreground))]">No action</span>;
  }

  return (
    <div className="space-y-2">
      <button className="btn btn-secondary btn-sm" disabled={pending} onClick={() => void onExecute()} type="button">
        {pending ? "Working..." : action === "start" ? "Start" : "Stop"}
      </button>
      {message ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{message}</p> : null}
    </div>
  );
}

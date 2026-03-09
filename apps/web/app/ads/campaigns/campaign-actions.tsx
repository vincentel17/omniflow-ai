"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type Props = {
  campaignId: string;
  status: string;
};

type ActionType = "request-activation" | "activate" | "pause";

function contextHeaders(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role,
  };
}

async function postAction(campaignId: string, action: ActionType): Promise<Response> {
  return fetch(`${getApiBaseUrl()}/ads/campaigns/${campaignId}/${action}`, {
    method: "POST",
    headers: contextHeaders(),
    credentials: "include",
  });
}

function actionForStatus(status: string): ActionType | null {
  const normalized = status.toLowerCase();
  if (normalized === "draft") {
    return "request-activation";
  }
  if (normalized === "pending_activation" || normalized === "paused") {
    return "activate";
  }
  if (normalized === "active") {
    return "pause";
  }
  return null;
}

function actionLabel(action: ActionType): string {
  if (action === "request-activation") {
    return "Request Activation";
  }
  if (action === "activate") {
    return "Activate";
  }
  return "Pause";
}

export function CampaignActions({ campaignId, status }: Props) {
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
      const response = await postAction(campaignId, action);
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
        {pending ? "Working..." : actionLabel(action)}
      </button>
      {message ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{message}</p> : null}
    </div>
  );
}


"use client";

import { useState } from "react";

import { getApiBaseUrl } from "../../../lib/dev-context";

type Props = {
  creativeId: string;
  status: string;
};

export function CreativeActions({ creativeId, status }: Props) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const approved = status.toLowerCase() === "approved";

  async function onApprove(): Promise<void> {
    if (approved || pending) {
      return;
    }
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/ads/creatives/${creativeId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });
      if (!response.ok) {
        setMessage(`Approve failed (${response.status})`);
        return;
      }
      setMessage("Approved. Refreshing...");
      window.location.reload();
    } catch {
      setMessage("Approve failed (network error).");
    } finally {
      setPending(false);
    }
  }

  if (approved) {
    return <span className="text-xs text-[rgb(var(--muted-foreground))]">Approved</span>;
  }

  return (
    <div className="space-y-2">
      <button className="btn btn-secondary btn-sm" disabled={pending} onClick={() => void onApprove()} type="button">
        {pending ? "Approving..." : "Approve"}
      </button>
      {message ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{message}</p> : null}
    </div>
  );
}

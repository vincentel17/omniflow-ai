"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { ApiError } from "../../../lib/api";
import { runAgents, updateAgentDefinition } from "../../../lib/api";
import { ButtonGhost } from "../../../components/ui/primitives";

function renderError(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "message" in error && typeof (error as ApiError).message === "string") {
    const typedError = error as ApiError;
    return typedError.requestId ? `${typedError.message} [request_id=${typedError.requestId}]` : typedError.message;
  }
  return fallback;
}

export function AgentsPageActions() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function runNow() {
    setPending(true);
    setStatus(null);
    try {
      await runAgents("manual");
      setStatus("Agent run requested.");
      router.refresh();
    } catch (error) {
      setStatus(renderError(error, "Agent run request failed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-2">
      <ButtonGhost className="w-full" data-testid="tour-agent-run" disabled={pending} onClick={() => void runNow()} type="button">
        {pending ? "Running..." : "Run Agents Now"}
      </ButtonGhost>
      {status ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{status}</p> : null}
    </div>
  );
}

export function AgentToggleButton({ name, nextEnabled }: { name: string; nextEnabled: boolean }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function toggle() {
    setPending(true);
    setStatus(null);
    try {
      await updateAgentDefinition(name, nextEnabled);
      setStatus(nextEnabled ? "Agent enabled." : "Agent disabled.");
      router.refresh();
    } catch (error) {
      setStatus(renderError(error, "Agent update failed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <ButtonGhost disabled={pending} onClick={() => void toggle()} type="button">
        {pending ? "Saving..." : nextEnabled ? "Enable" : "Disable"}
      </ButtonGhost>
      {status ? <p className="text-xs text-[rgb(var(--muted-foreground))]">{status}</p> : null}
    </div>
  );
}

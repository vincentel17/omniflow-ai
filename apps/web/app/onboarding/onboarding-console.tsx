"use client";

import { useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";

type Session = {
  id: string;
  status: "in_progress" | "completed";
  steps_json: Record<string, boolean>;
  created_at: string;
  completed_at: string | null;
};

const DEFAULT_STEPS = [
  "select_vertical_pack",
  "create_brand_profile",
  "connect_account",
  "run_presence_audit",
  "generate_campaign_plan",
  "generate_content_items",
  "approve_schedule_first_post",
  "ingest_mock_inbox_interaction",
  "create_and_route_lead"
];

export function OnboardingConsole() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshStatus() {
    const response = await fetch(`${getApiBaseUrl()}/onboarding/status`, {
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });
    if (!response.ok) {
      setMessage(`Failed to load onboarding status (${response.status})`);
      return;
    }
    setSession(await response.json());
  }

  async function startSession() {
    setLoading(true);
    setMessage(null);
    const response = await fetch(`${getApiBaseUrl()}/onboarding/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });
    setLoading(false);
    if (!response.ok) {
      setMessage(`Failed to start onboarding (${response.status})`);
      return;
    }
    setSession(await response.json());
  }

  async function completeStep(stepId: string) {
    setLoading(true);
    setMessage(null);
    const response = await fetch(`${getApiBaseUrl()}/onboarding/step/${stepId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ completed: true })
    });
    setLoading(false);
    if (!response.ok) {
      setMessage(`Failed to complete ${stepId} (${response.status})`);
      return;
    }
    setSession(await response.json());
  }

  useEffect(() => {
    void refreshStatus();
  }, []);

  const steps = useMemo(() => {
    const state = session?.steps_json ?? {};
    return DEFAULT_STEPS.map((id) => ({ id, done: Boolean(state[id]) }));
  }, [session]);

  const doneCount = steps.filter((step) => step.done).length;
  const percent = steps.length === 0 ? 0 : Math.round((doneCount / steps.length) * 100);

  return (
    <div className="page-shell space-y-6">
      <div className="surface-card-hero space-y-3 p-5">
        <h1 className="text-2xl font-semibold tracking-tight text-[rgb(var(--card-foreground))]">Pilot Onboarding</h1>
        <p className="text-sm text-[rgb(var(--muted-foreground))]">Guided 30-day content-to-lead sprint checklist.</p>
        <div className="text-sm text-[rgb(var(--muted-foreground))]">Progress: {doneCount}/{steps.length} ({percent}%)</div>
        <div className="h-2 w-full rounded bg-[rgb(var(--muted))]">
          <div className="h-2 rounded bg-[rgb(var(--success))]" style={{ width: `${percent}%` }} />
        </div>
        <button
          className="btn-enterprise btn-enterprise-primary mt-2"
          data-testid="tour-onboarding-create-org"
          disabled={loading}
          onClick={startSession}
          type="button"
        >
          {session ? "Restart/Resume Session" : "Start Onboarding"}
        </button>
      </div>

      <div className="surface-card p-5">
        <h2 className="text-lg font-medium text-[rgb(var(--card-foreground))]">Steps</h2>
        <ul className="mt-3 space-y-2">
          {steps.map((step) => (
            <li className="flex items-center justify-between rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] px-3 py-2" key={step.id}>
              <span className="text-sm text-[rgb(var(--card-foreground))]">{step.id}</span>
              {step.done ? (
                <span className="text-xs text-[rgb(var(--success))]">Completed</span>
              ) : (
                <button
                  className="btn-enterprise btn-enterprise-secondary px-2 py-1 text-xs"
                  data-testid={step.id === "select_vertical_pack" ? "tour-pack-select" : `onboarding-step-${step.id}`}
                  disabled={loading || !session}
                  onClick={() => completeStep(step.id)}
                  type="button"
                >
                  Mark complete
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>

      {message ? (
        <p className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--card-foreground))]" data-testid="onboarding-message">
          {message}
        </p>
      ) : null}
    </div>
  );
}

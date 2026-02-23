"use client";

import { useEffect, useMemo, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

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

function apiHeaders(): HeadersInit {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role
  };
}

export function OnboardingConsole() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refreshStatus() {
    const response = await fetch(`${getApiBaseUrl()}/onboarding/status`, { headers: apiHeaders() });
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
      headers: apiHeaders()
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
      headers: apiHeaders(),
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
    <div className="space-y-6 p-6 text-slate-100">
      <div className="rounded border border-slate-700 bg-slate-900 p-4">
        <h1 className="text-xl font-semibold">Pilot Onboarding</h1>
        <p className="mt-1 text-sm text-slate-300">Guided 30-day content-to-lead sprint checklist.</p>
        <div className="mt-3 text-sm text-slate-300">Progress: {doneCount}/{steps.length} ({percent}%)</div>
        <div className="mt-2 h-2 w-full rounded bg-slate-700">
          <div className="h-2 rounded bg-emerald-400" style={{ width: `${percent}%` }} />
        </div>
        <button className="mt-4 rounded bg-slate-200 px-3 py-2 text-slate-900" disabled={loading} onClick={startSession} type="button">
          {session ? "Restart/Resume Session" : "Start Onboarding"}
        </button>
      </div>

      <div className="rounded border border-slate-700 bg-slate-900 p-4">
        <h2 className="text-lg font-medium">Steps</h2>
        <ul className="mt-3 space-y-2">
          {steps.map((step) => (
            <li className="flex items-center justify-between rounded border border-slate-800 px-3 py-2" key={step.id}>
              <span className="text-sm">{step.id}</span>
              {step.done ? (
                <span className="text-xs text-emerald-300">Completed</span>
              ) : (
                <button
                  className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200"
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

      {message ? <p className="text-sm text-amber-300">{message}</p> : null}
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";

import { getApiBaseUrl } from "../../lib/dev-context";
import { readApiError } from "../../lib/http";

type Lead = {
  id: string;
  source: string;
  status: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  tags_json: string[];
  created_at: string;
};

type Score = { score_total: number; score_json: Record<string, unknown> };
type Assignment = { assigned_to_user_id: string; rule_applied: string };
type NurtureTask = {
  id: string;
  type: string;
  due_at: string;
  status: string;
  template_key: string | null;
};
type NextBestAction = {
  action_type: string;
  rationale: string;
  expected_uplift: number;
  confidence_score: number;
};

type Props = { initialLeads: Lead[] };

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json",
  };
}

export function LeadsConsole({ initialLeads }: Props) {
  const [leads, setLeads] = useState(initialLeads);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(initialLeads[0]?.id ?? null);
  const [score, setScore] = useState<Score | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [tasks, setTasks] = useState<NurtureTask[]>([]);
  const [nextBestAction, setNextBestAction] = useState<NextBestAction | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const selectedLead = useMemo(
    () => leads.find((item) => item.id === selectedLeadId) ?? null,
    [leads, selectedLeadId],
  );

  async function refreshLeads() {
    setPendingAction("refresh");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/leads?limit=50&offset=0`, {
        headers: headers(),
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) {
        setStatus(await readApiError(response, "Refresh failed"));
        return;
      }
      setLeads((await response.json()) as Lead[]);
    } catch {
      setStatus("Refresh failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function loadTasks(leadId: string) {
    try {
      const response = await fetch(`${getApiBaseUrl()}/leads/${leadId}/nurture/tasks?limit=50&offset=0`, {
        headers: headers(),
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) return;
      setTasks((await response.json()) as NurtureTask[]);
    } catch {
      setStatus("Load tasks failed (network error).");
    }
  }

  async function loadNextBestAction(leadId: string) {
    try {
      const response = await fetch(`${getApiBaseUrl()}/optimization/next-best-action/lead/${leadId}`, {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) {
        setNextBestAction(null);
        return;
      }
      setNextBestAction((await response.json()) as NextBestAction);
    } catch {
      setNextBestAction(null);
    }
  }

  async function scoreLead() {
    if (!selectedLead) return;
    setPendingAction("score");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/leads/${selectedLead.id}/score`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
      });
      if (!response.ok) {
        setStatus(await readApiError(response, "Score failed"));
        return;
      }
      setScore((await response.json()) as Score);
      setStatus("Lead scored.");
    } catch {
      setStatus("Score failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function routeLead() {
    if (!selectedLead) return;
    setPendingAction("route");
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/leads/${selectedLead.id}/route`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
      });
      if (!response.ok) {
        setStatus(await readApiError(response, "Route failed"));
        return;
      }
      setAssignment((await response.json()) as Assignment);
      setStatus("Lead routed.");
      await loadTasks(selectedLead.id);
    } catch {
      setStatus("Route failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function applyNurture() {
    if (!selectedLead) return;
    setPendingAction("nurture");
    setStatus(null);
    try {
      const suggest = await fetch(`${getApiBaseUrl()}/leads/${selectedLead.id}/nurture/suggest`, {
        method: "POST",
        headers: headers(),
        credentials: "include",
      });
      if (!suggest.ok) {
        setStatus(await readApiError(suggest, "Suggest nurture failed"));
        return;
      }
      const plan = (await suggest.json()) as { tasks: Array<Record<string, unknown>> };
      const apply = await fetch(`${getApiBaseUrl()}/leads/${selectedLead.id}/nurture/apply`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tasks: plan.tasks }),
        credentials: "include",
      });
      if (!apply.ok) {
        setStatus(await readApiError(apply, "Apply nurture failed"));
        return;
      }
      setStatus("Nurture tasks applied.");
      await loadTasks(selectedLead.id);
    } catch {
      setStatus("Apply nurture failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  async function markTaskDone(taskId: string) {
    if (!selectedLead) return;
    setPendingAction(`task-${taskId}`);
    setStatus(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/leads/${selectedLead.id}/nurture/tasks/${taskId}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({ status: "done" }),
        credentials: "include",
      });
      if (!response.ok) {
        setStatus(await readApiError(response, "Task update failed"));
        return;
      }
      setStatus("Task marked done.");
      await loadTasks(selectedLead.id);
    } catch {
      setStatus("Task update failed (network error).");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-2">
      <section className="surface-card ui-fade-in p-4">
        <button className="btn-enterprise btn-enterprise-secondary" data-testid="leads-refresh" disabled={pendingAction !== null} onClick={refreshLeads} type="button">
          {pendingAction === "refresh" ? "Refreshing..." : "Refresh"}
        </button>
        <ul className="mt-4 space-y-2">
          {leads.map((lead) => (
            <li className="ui-hover-lift rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-3" key={lead.id}>
              <button
                className="focus-ring w-full rounded text-left"
                data-testid={leads[0]?.id === lead.id ? "lead-open-first" : `lead-open-${lead.id}`}
                onClick={() => {
                  setSelectedLeadId(lead.id);
                  void loadTasks(lead.id);
                  void loadNextBestAction(lead.id);
                }}
                type="button"
              >
                <p className="font-medium text-[rgb(var(--card-foreground))]">{lead.name ?? "Unnamed Lead"}</p>
                <p className="text-sm text-[rgb(var(--muted-foreground))]">
                  {lead.status} | {lead.source}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="surface-card ui-fade-in p-4">
        <h2 className="text-lg font-semibold text-[rgb(var(--card-foreground))]">Lead Detail</h2>
        {selectedLead ? (
          <>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="btn-enterprise btn-enterprise-secondary" data-testid="lead-score-btn" disabled={pendingAction !== null} onClick={scoreLead} type="button">
                Score
              </button>
              <button className="btn-enterprise btn-enterprise-secondary" data-testid="lead-route-btn" disabled={pendingAction !== null} onClick={routeLead} type="button">
                Route
              </button>
              <button className="btn-enterprise btn-enterprise-primary" data-testid="lead-apply-nurture-btn" disabled={pendingAction !== null} onClick={applyNurture} type="button">
                Apply Nurture
              </button>
            </div>
            {score ? (
              <pre className="mt-3 overflow-auto rounded-lg bg-[rgb(var(--muted))] p-2 text-xs ui-fade-in">{JSON.stringify(score, null, 2)}</pre>
            ) : null}
            {assignment ? (
              <p className="mt-3 text-sm text-[rgb(var(--muted-foreground))] ui-fade-in">
                Assigned to {assignment.assigned_to_user_id} via {assignment.rule_applied}
              </p>
            ) : null}
            <h3 className="mt-4 font-medium text-[rgb(var(--card-foreground))]">Next Best Action</h3>
            {nextBestAction ? (
              <div className="mt-2 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] p-2 text-sm ui-fade-in">
                <p className="font-medium text-[rgb(var(--card-foreground))]">{nextBestAction.action_type}</p>
                <p className="text-[rgb(var(--card-foreground))]">{nextBestAction.rationale}</p>
                <p className="text-[rgb(var(--muted-foreground))]">
                  Expected uplift: {(nextBestAction.expected_uplift * 100).toFixed(1)}% | Confidence:{" "}
                  {(nextBestAction.confidence_score * 100).toFixed(1)}%
                </p>
              </div>
            ) : (
              <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))] ui-pulse-soft">No next-best-action suggestion available.</p>
            )}
            <h3 className="mt-4 font-medium text-[rgb(var(--card-foreground))]">Nurture Tasks</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {tasks.map((task) => (
                <li className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-2 ui-hover-lift" key={task.id}>
                  <div className="flex items-center justify-between gap-2">
                    <span>
                      {task.type} | {task.status} | {task.template_key ?? "manual"}
                    </span>
                    {task.status !== "done" ? (
                      <button
                        className="btn-enterprise btn-enterprise-secondary px-2 py-1 text-xs"
                        data-testid={`lead-task-done-${task.id}`}
                        disabled={pendingAction !== null}
                        onClick={() => markTaskDone(task.id)}
                        type="button"
                      >
                        Mark Done
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-3 text-[rgb(var(--muted-foreground))] ui-pulse-soft">Select a lead.</p>
        )}
        {status ? (
          <p className="mt-3 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--muted))] px-3 py-2 text-sm text-[rgb(var(--card-foreground))] ui-fade-in" data-testid="lead-status-message">
            {status}
          </p>
        ) : null}
      </section>
    </div>
  );
}

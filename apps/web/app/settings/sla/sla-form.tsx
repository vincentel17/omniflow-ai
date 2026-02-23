"use client";

import { FormEvent, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../lib/dev-context";

type SlaConfig = {
  response_time_minutes: number;
  escalation_minutes: number;
  notify_channels_json: string[];
};

type Props = { initial: SlaConfig | null };

export function SlaForm({ initial }: Props) {
  const [responseMinutes, setResponseMinutes] = useState(initial?.response_time_minutes ?? 30);
  const [escalationMinutes, setEscalationMinutes] = useState(initial?.escalation_minutes ?? 60);
  const [status, setStatus] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const context = getDevContext();
    const response = await fetch(`${getApiBaseUrl()}/sla/config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Omniflow-User-Id": context.userId,
        "X-Omniflow-Org-Id": context.orgId,
        "X-Omniflow-Role": context.role
      },
      body: JSON.stringify({
        response_time_minutes: responseMinutes,
        escalation_minutes: escalationMinutes,
        notify_channels_json: ["in_app"]
      })
    });
    if (!response.ok) {
      setStatus(`Save failed (${response.status})`);
      return;
    }
    setStatus("SLA saved.");
  }

  return (
    <form className="mt-6 max-w-xl space-y-4 rounded border border-slate-800 p-4" onSubmit={submit}>
      <label className="block text-sm">
        <span className="text-slate-300">Response Time (minutes)</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
          min={1}
          onChange={(event) => setResponseMinutes(Number(event.target.value))}
          type="number"
          value={responseMinutes}
        />
      </label>
      <label className="block text-sm">
        <span className="text-slate-300">Escalation Time (minutes)</span>
        <input
          className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2"
          min={1}
          onChange={(event) => setEscalationMinutes(Number(event.target.value))}
          type="number"
          value={escalationMinutes}
        />
      </label>
      <button className="rounded bg-slate-200 px-4 py-2 text-slate-900" type="submit">
        Save SLA
      </button>
      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </form>
  );
}

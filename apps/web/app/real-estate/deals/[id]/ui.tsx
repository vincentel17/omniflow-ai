"use client";

import { useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../../../lib/dev-context";

type ChecklistItem = {
  id: string;
  title: string;
  status: string;
  due_at: string | null;
};

type DocumentRequest = {
  id: string;
  doc_type: string;
  requested_from: string;
  status: string;
};

type Communication = {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body_text: string;
};

type Props = {
  dealId: string;
  initialChecklist: ChecklistItem[];
  initialDocuments: DocumentRequest[];
  initialCommunications: Communication[];
};

function headers(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role
  };
}

export function DealDetailConsole({ dealId, initialChecklist, initialDocuments, initialCommunications }: Props) {
  const [checklist, setChecklist] = useState<ChecklistItem[]>(initialChecklist);
  const [documents, setDocuments] = useState<DocumentRequest[]>(initialDocuments);
  const [communications, setCommunications] = useState<Communication[]>(initialCommunications);
  const [status, setStatus] = useState<string | null>(null);

  async function refresh() {
    const [c, d, m] = await Promise.all([
      fetch(`${getApiBaseUrl()}/re/deals/${dealId}/checklist-items?limit=100&offset=0`, { headers: headers(), cache: "no-store" }),
      fetch(`${getApiBaseUrl()}/re/deals/${dealId}/documents?limit=100&offset=0`, { headers: headers(), cache: "no-store" }),
      fetch(`${getApiBaseUrl()}/re/deals/${dealId}/communications?limit=100&offset=0`, { headers: headers(), cache: "no-store" })
    ]);
    if (!c.ok || !d.ok || !m.ok) {
      setStatus("Refresh failed.");
      return;
    }
    setChecklist((await c.json()) as ChecklistItem[]);
    setDocuments((await d.json()) as DocumentRequest[]);
    setCommunications((await m.json()) as Communication[]);
  }

  async function applyChecklist() {
    const response = await fetch(`${getApiBaseUrl()}/re/deals/${dealId}/checklists/apply-template`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ template_name: "under_contract_core" })
    });
    if (!response.ok) {
      setStatus(`Apply checklist failed (${response.status})`);
      return;
    }
    setStatus("Checklist applied.");
    await refresh();
  }

  async function completeChecklistItem(itemId: string) {
    const response = await fetch(`${getApiBaseUrl()}/re/deals/${dealId}/checklist-items/${itemId}/complete`, {
      method: "POST",
      headers: headers()
    });
    if (!response.ok) {
      setStatus(`Complete failed (${response.status})`);
      return;
    }
    setStatus("Checklist item completed.");
    await refresh();
  }

  async function addDocumentRequest() {
    const response = await fetch(`${getApiBaseUrl()}/re/deals/${dealId}/documents/request`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ doc_type: "inspection", requested_from: "client" })
    });
    if (!response.ok) {
      setStatus(`Document request failed (${response.status})`);
      return;
    }
    setStatus("Document request added.");
    await refresh();
  }

  async function addCommunication() {
    const response = await fetch(`${getApiBaseUrl()}/re/deals/${dealId}/communications/log`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ channel: "note", direction: "outbound", subject: "Update", body_text: "Shared timeline with client." })
    });
    if (!response.ok) {
      setStatus(`Communication log failed (${response.status})`);
      return;
    }
    setStatus("Communication logged.");
    await refresh();
  }

  return (
    <div className="mt-6 grid gap-6">
      <section className="rounded border border-slate-800 p-4">
        <div className="flex gap-2">
          <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" type="button" onClick={applyChecklist}>
            Apply Checklist
          </button>
          <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={addDocumentRequest}>
            Request Document
          </button>
          <button className="rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={addCommunication}>
            Log Communication
          </button>
        </div>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Checklist</h2>
        <ul className="mt-3 space-y-2">
          {checklist.map((item) => (
            <li className="rounded border border-slate-700 p-3" key={item.id}>
              <p className="font-medium">
                {item.title} | {item.status}
              </p>
              <p className="text-sm text-slate-400">{item.due_at ?? "No due date"}</p>
              {item.status !== "done" ? (
                <button className="mt-2 rounded bg-slate-700 px-3 py-1 text-sm" type="button" onClick={() => completeChecklistItem(item.id)}>
                  Mark Done
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Document Requests</h2>
        <ul className="mt-3 space-y-2">
          {documents.map((doc) => (
            <li className="rounded border border-slate-700 p-3" key={doc.id}>
              <p className="font-medium">
                {doc.doc_type} | {doc.requested_from}
              </p>
              <p className="text-sm text-slate-400">{doc.status}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-xl font-semibold">Communication Log</h2>
        <ul className="mt-3 space-y-2">
          {communications.map((comm) => (
            <li className="rounded border border-slate-700 p-3" key={comm.id}>
              <p className="font-medium">
                {comm.channel} | {comm.direction}
              </p>
              <p className="text-sm text-slate-300">{comm.subject ?? "No subject"}</p>
              <p className="text-sm text-slate-400">{comm.body_text}</p>
            </li>
          ))}
        </ul>
      </section>

      {status ? <p className="text-sm text-slate-300">{status}</p> : null}
    </div>
  );
}


"use client";

import { useMemo, useState } from "react";

import { getApiBaseUrl, getDevContext } from "../../lib/dev-context";

type Thread = {
  id: string;
  provider: string;
  account_ref: string;
  subject: string | null;
  status: string;
  assigned_to_user_id: string | null;
  last_message_at: string | null;
  lead_id: string | null;
};

type Message = {
  id: string;
  direction: string;
  sender_display: string;
  body_text: string;
  created_at: string;
  flags_json: Record<string, boolean>;
};

type Props = { initialThreads: Thread[] };

function headers(): Record<string, string> {
  const context = getDevContext();
  return {
    "Content-Type": "application/json",
    "X-Omniflow-User-Id": context.userId,
    "X-Omniflow-Org-Id": context.orgId,
    "X-Omniflow-Role": context.role
  };
}

export function InboxConsole({ initialThreads }: Props) {
  const [threads, setThreads] = useState(initialThreads);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(initialThreads[0]?.id ?? null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const selectedThread = useMemo(() => threads.find((item) => item.id === selectedThreadId) ?? null, [threads, selectedThreadId]);

  async function refreshThreads() {
    const response = await fetch(`${getApiBaseUrl()}/inbox/threads?limit=50&offset=0`, { headers: headers(), cache: "no-store" });
    if (!response.ok) {
      setStatus(`Refresh failed (${response.status})`);
      return;
    }
    const data = (await response.json()) as Thread[];
    setThreads(data);
  }

  async function loadMessages(threadId: string) {
    setSelectedThreadId(threadId);
    const response = await fetch(`${getApiBaseUrl()}/inbox/threads/${threadId}/messages?limit=100&offset=0`, { headers: headers(), cache: "no-store" });
    if (!response.ok) {
      setStatus(`Load messages failed (${response.status})`);
      return;
    }
    setMessages((await response.json()) as Message[]);
  }

  async function ingestMock() {
    const response = await fetch(`${getApiBaseUrl()}/inbox/ingest/mock`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        thread: {
          provider: "meta",
          account_ref: "acct-main",
          external_thread_id: `ui-${Date.now()}`,
          thread_type: "dm",
          subject: "Mock inbound",
          participants_json: [{ id: "prospect-1", display: "Prospect" }],
          last_message_at: new Date().toISOString()
        },
        messages: [
          {
            external_message_id: `ui-msg-${Date.now()}`,
            direction: "inbound",
            sender_ref: "prospect-1",
            sender_display: "Prospect",
            body_text: "Need help buying soon. Contact me at prospect@example.com",
            body_raw_json: {}
          }
        ]
      })
    });
    if (!response.ok) {
      setStatus(`Ingest failed (${response.status})`);
      return;
    }
    setStatus("Mock inbound ingested.");
    await refreshThreads();
  }

  async function suggestReply() {
    if (!selectedThread) return;
    const response = await fetch(`${getApiBaseUrl()}/inbox/threads/${selectedThread.id}/suggest-reply`, {
      method: "POST",
      headers: headers()
    });
    if (!response.ok) {
      setStatus(`Suggest failed (${response.status})`);
      return;
    }
    const payload = (await response.json()) as { reply_text: string };
    setDraftText(payload.reply_text);
    setStatus("Reply suggestion generated.");
  }

  async function draftReply() {
    if (!selectedThread) return;
    const response = await fetch(`${getApiBaseUrl()}/inbox/threads/${selectedThread.id}/draft-reply`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ body_text: draftText || "Thanks, we will follow up shortly." })
    });
    if (!response.ok) {
      setStatus(`Draft failed (${response.status})`);
      return;
    }
    setStatus("Draft reply saved.");
    await loadMessages(selectedThread.id);
  }

  async function createLead() {
    if (!selectedThread) return;
    const response = await fetch(`${getApiBaseUrl()}/leads/from-thread/${selectedThread.id}`, {
      method: "POST",
      headers: headers()
    });
    if (!response.ok) {
      setStatus(`Lead creation failed (${response.status})`);
      return;
    }
    setStatus("Lead created from thread.");
    await refreshThreads();
  }

  async function closeThread() {
    if (!selectedThread) return;
    const response = await fetch(`${getApiBaseUrl()}/inbox/threads/${selectedThread.id}/close`, {
      method: "POST",
      headers: headers()
    });
    if (!response.ok) {
      setStatus(`Close failed (${response.status})`);
      return;
    }
    setStatus("Thread closed.");
    await refreshThreads();
  }

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-2">
      <section className="rounded border border-slate-800 p-4">
        <div className="flex gap-2">
          <button className="rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" onClick={ingestMock} type="button">
            Ingest Mock
          </button>
          <button className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={refreshThreads} type="button">
            Refresh
          </button>
        </div>
        <ul className="mt-4 space-y-2">
          {threads.map((thread) => (
            <li className="rounded border border-slate-800 p-3" key={thread.id}>
              <button className="w-full text-left" onClick={() => loadMessages(thread.id)} type="button">
                <p className="font-medium">
                  {thread.provider} | {thread.status}
                </p>
                <p className="text-sm text-slate-400">{thread.subject ?? "No subject"}</p>
                {thread.lead_id ? <p className="text-xs text-emerald-300">Lead linked</p> : null}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border border-slate-800 p-4">
        <h2 className="text-lg font-semibold">Thread Detail</h2>
        {selectedThread ? (
          <>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={suggestReply} type="button">
                Suggest Reply
              </button>
              <button className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={createLead} type="button">
                Create Lead
              </button>
              <button className="rounded bg-slate-700 px-3 py-1 text-sm" onClick={closeThread} type="button">
                Close
              </button>
            </div>
            <textarea
              className="mt-3 h-24 w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm"
              onChange={(event) => setDraftText(event.target.value)}
              placeholder="Draft reply text..."
              value={draftText}
            />
            <button className="mt-2 rounded bg-slate-200 px-3 py-1 text-sm text-slate-900" onClick={draftReply} type="button">
              Save Draft
            </button>
            <ul className="mt-4 space-y-2">
              {messages.map((message) => (
                <li className="rounded border border-slate-800 p-2 text-sm" key={message.id}>
                  <p className="font-medium">
                    {message.direction} - {message.sender_display}
                  </p>
                  <p>{message.body_text}</p>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-3 text-slate-400">Select a thread to view details.</p>
        )}
        {status ? <p className="mt-3 text-sm text-slate-300">{status}</p> : null}
      </section>
    </div>
  );
}

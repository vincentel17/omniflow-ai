import { apiFetch } from "../../lib/api";
import { InboxConsole } from "./console";

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

async function getThreads(): Promise<Thread[]> {
  return apiFetch<Thread[]>("/inbox/threads?limit=50&offset=0");
}

export default async function InboxPage() {
  const threads = await getThreads();
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Inbox</h1>
      <p className="mt-2 text-slate-300">Ingest interactions, review conversations, draft replies, and convert to leads.</p>
      <InboxConsole initialThreads={threads} />
    </main>
  );
}

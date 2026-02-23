import Link from "next/link";

export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">Settings</h1>
      <ul className="mt-6 space-y-3 text-slate-300">
        <li>
          <Link className="underline" href="/settings/verticals">
            Vertical Pack Selection
          </Link>
        </li>
        <li>
          <Link className="underline" href="/settings/brand">
            Brand Profile
          </Link>
        </li>
        <li>
          <Link className="underline" href="/settings/sla">
            SLA Settings
          </Link>
        </li>
        <li>
          <Link className="underline" href="/inbox">
            Inbox
          </Link>
        </li>
        <li>
          <Link className="underline" href="/leads">
            Leads
          </Link>
        </li>
        <li>
          <Link className="underline" href="/events">
            Event Stream
          </Link>
        </li>
        <li>
          <Link className="underline" href="/audit">
            Audit Log
          </Link>
        </li>
      </ul>
    </main>
  );
}

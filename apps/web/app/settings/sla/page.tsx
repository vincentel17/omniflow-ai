import { apiFetch } from "../../../lib/api";
import { SlaForm } from "./sla-form";

type SlaConfig = {
  response_time_minutes: number;
  escalation_minutes: number;
  notify_channels_json: string[];
};

async function getSlaConfig(): Promise<SlaConfig | null> {
  try {
    return await apiFetch<SlaConfig>("/sla/config");
  } catch {
    return null;
  }
}

export default async function SlaSettingsPage() {
  const initial = await getSlaConfig();
  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <h1 className="text-3xl font-semibold">SLA Settings</h1>
      <p className="mt-2 text-slate-300">Define response windows and escalation thresholds for inbound threads.</p>
      <SlaForm initial={initial} />
    </main>
  );
}

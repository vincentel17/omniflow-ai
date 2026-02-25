import { apiFetch } from "../../../lib/api";
import { VerticalSelector } from "./vertical-selector";

type PackListResponse = {
  packs: string[];
};

type CurrentPack = {
  id: string;
  org_id: string;
  pack_slug: string;
  created_at: string;
};

async function getPacks(): Promise<string[]> {
  const result = await apiFetch<PackListResponse>("/verticals/packs");
  return result.packs;
}

async function getCurrentPack(): Promise<string | null> {
  try {
    const current = await apiFetch<CurrentPack>("/verticals/current");
    return current.pack_slug;
  } catch {
    return null;
  }
}

export default async function VerticalSettingsPage() {
  const [packs, currentPack] = await Promise.all([getPacks(), getCurrentPack()]);
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Vertical Packs</h1>
      <p className="mt-2 text-slate-300">Select the active pack for the current organization.</p>
      <p className="mt-4 text-sm text-slate-400">Current: {currentPack ?? "none selected"}</p>
      <VerticalSelector packs={packs} />
    </main>
  );
}


import { apiFetch, type VerticalPackManifest } from "../../../lib/api";
import { VerticalSelector } from "./vertical-selector";

type CurrentPack = {
  id: string;
  org_id: string;
  pack_slug: string;
  created_at: string;
};

async function getPacks(): Promise<VerticalPackManifest[]> {
  return apiFetch<VerticalPackManifest[]>("/verticals/available");
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
  const active = packs.find((pack) => pack.slug === currentPack) ?? null;

  return (
    <main className="page-shell space-y-6">
      <section className="surface-card p-6">
        <h1 className="page-title">Vertical Packs</h1>
        <p className="page-subtitle">Activate one validated industry pack for this org. Activation is plan-gated and audited.</p>
        <p className="mt-3 text-sm text-[rgb(var(--muted-foreground))]">Current: {currentPack ?? "none selected"}</p>
      </section>

      {active ? (
        <section className="surface-card p-4 text-sm text-[rgb(var(--muted-foreground))]">
          <p className="font-medium text-[rgb(var(--foreground))]">Active manifest</p>
          <p className="mt-2">{active.name} ({active.slug}) v{active.version}</p>
          <p>Core compatibility: {active.compatible_core_version}</p>
          <p className="break-all">Checksum: {active.checksum}</p>
        </section>
      ) : null}

      <VerticalSelector currentPack={currentPack} packs={packs} />
    </main>
  );
}

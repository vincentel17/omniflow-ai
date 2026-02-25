import { apiFetch } from "../../../lib/api";
import { BrandProfileForm } from "./profile-form";

type BrandProfile = {
  id: string;
  org_id: string;
  brand_voice_json: Record<string, unknown>;
  brand_assets_json: Record<string, unknown>;
  locations_json: Array<Record<string, unknown>>;
  auto_approve_tiers_max: number;
  require_approval_for_publish: boolean;
};

async function getProfile(): Promise<BrandProfile | null> {
  try {
    return await apiFetch<BrandProfile>("/brand/profile");
  } catch {
    return null;
  }
}

export default async function BrandSettingsPage() {
  const profile = await getProfile();
  return (
    <main className="page-shell">
      <h1 className="text-3xl font-semibold">Brand Profile</h1>
      <p className="mt-2 text-slate-300">Configure brand voice and approval thresholds.</p>
      <BrandProfileForm initial={profile} />
    </main>
  );
}


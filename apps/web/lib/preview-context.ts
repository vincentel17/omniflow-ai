export type PreviewOrgKey = "alpha" | "beta" | "gamma";
export type PreviewRole = "owner" | "admin" | "member" | "agent";

export type DevContext = {
  userId: string;
  orgId: string;
  orgName: string;
  role: PreviewRole;
  previewOrg: PreviewOrgKey;
};

export const PREVIEW_ORG_COOKIE = "omniflow_preview_org";
export const PREVIEW_ROLE_COOKIE = "omniflow_preview_role";

export const previewOrgs: Record<PreviewOrgKey, { id: string; name: string }> = {
  alpha: {
    id: "012f410d-8a1a-593a-9ae0-d7a8dd41a209",
    name: "OmniFlow Home Care Demo",
  },
  beta: {
    id: "18826643-91da-5dd4-b088-03a36d6f72a5",
    name: "OmniFlow Real Estate Demo",
  },
  gamma: {
    id: "8f4a63c6-f07e-51b3-9417-67543a1da993",
    name: "OmniFlow Generic Demo",
  },
};

export const previewUsers: Record<PreviewRole, string> = {
  owner: "7e03f43e-9e88-5d95-bb87-1780a0a618a2",
  admin: "312267a8-0347-520a-87f0-794836f70397",
  member: "99f266b8-163e-59c8-a7b9-98527c383061",
  agent: "dec329b3-ea5e-5451-8584-be91eb79d856",
};

const DEFAULT_PREVIEW_ORG: PreviewOrgKey = "beta";
const DEFAULT_PREVIEW_ROLE: PreviewRole = "owner";

function isPreviewOrg(value: string | undefined): value is PreviewOrgKey {
  return value === "alpha" || value === "beta" || value === "gamma";
}

function isPreviewRole(value: string | undefined): value is PreviewRole {
  return value === "owner" || value === "admin" || value === "member" || value === "agent";
}

export function normalizePreviewSelection(org: string | undefined, role: string | undefined): {
  previewOrg: PreviewOrgKey;
  previewRole: PreviewRole;
} {
  return {
    previewOrg: isPreviewOrg(org) ? org : DEFAULT_PREVIEW_ORG,
    previewRole: isPreviewRole(role) ? role : DEFAULT_PREVIEW_ROLE,
  };
}

export function buildDevContext(previewOrg: PreviewOrgKey, previewRole: PreviewRole): DevContext {
  const org = previewOrgs[previewOrg];
  return {
    userId: previewUsers[previewRole],
    orgId: org.id,
    orgName: org.name,
    role: previewRole,
    previewOrg,
  };
}

export function parseCookieHeader(cookieHeader: string | undefined): Record<string, string> {
  if (!cookieHeader) {
    return {};
  }

  return cookieHeader
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, part) => {
      const separator = part.indexOf("=");
      if (separator === -1) {
        return acc;
      }
      const key = part.slice(0, separator).trim();
      const value = decodeURIComponent(part.slice(separator + 1).trim());
      acc[key] = value;
      return acc;
    }, {});
}

export function resolveDevContextFromCookieHeader(cookieHeader: string | undefined): DevContext {
  const cookies = parseCookieHeader(cookieHeader);
  const { previewOrg, previewRole } = normalizePreviewSelection(cookies[PREVIEW_ORG_COOKIE], cookies[PREVIEW_ROLE_COOKIE]);
  return buildDevContext(previewOrg, previewRole);
}

export function getDefaultDevContext(): DevContext {
  const { previewOrg, previewRole } = normalizePreviewSelection(
    process.env.NEXT_PUBLIC_PREVIEW_ORG,
    process.env.NEXT_PUBLIC_PREVIEW_ROLE,
  );
  return buildDevContext(previewOrg, previewRole);
}

import { NextResponse } from "next/server";

import { PREVIEW_ORG_COOKIE, PREVIEW_ROLE_COOKIE, normalizePreviewSelection } from "../../../lib/preview-context";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    previewOrg?: string;
    previewRole?: string;
  };
  const selection = normalizePreviewSelection(body.previewOrg, body.previewRole);
  const response = NextResponse.json({ ok: true, ...selection });

  response.cookies.set(PREVIEW_ORG_COOKIE, selection.previewOrg, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  response.cookies.set(PREVIEW_ROLE_COOKIE, selection.previewRole, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });

  return response;
}

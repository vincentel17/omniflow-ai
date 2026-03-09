import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    { ok: false, message: "preview context is deprecated; use /auth session flow" },
    { status: 410 }
  );
}

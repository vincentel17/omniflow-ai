import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const SESSION_COOKIE_KEYS = ["omniflow_session", "session"];

function isPublicPath(pathname: string): boolean {
  if (pathname === "/auth") {
    return true;
  }
  if (pathname.startsWith("/auth/")) {
    return true;
  }
  if (pathname.startsWith("/_next/")) {
    return true;
  }
  if (pathname.startsWith("/api/")) {
    return true;
  }
  if (pathname === "/favicon.ico") {
    return true;
  }
  return false;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const hasSessionCookie = SESSION_COOKIE_KEYS.some((key) => Boolean(request.cookies.get(key)?.value));
  if (hasSessionCookie) {
    return NextResponse.next();
  }

  const authUrl = new URL("/auth", request.url);
  authUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(authUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"]
};

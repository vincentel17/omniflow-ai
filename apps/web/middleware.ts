import { NextResponse, type NextRequest } from "next/server";
import { hasValidSession } from "./lib/server-auth";

const protectedPrefixes = [
  "/admin",
  "/ads",
  "/analytics",
  "/approvals",
  "/audit",
  "/automations",
  "/billing",
  "/campaigns",
  "/compliance",
  "/content",
  "/dashboard",
  "/events",
  "/inbox",
  "/leads",
  "/optimization",
  "/presence",
  "/publish",
  "/real-estate",
  "/reputation",
  "/seo",
  "/settings"
];

function isProtectedPath(pathname: string): boolean {
  return protectedPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }
  const enforceAuth = request.nextUrl.searchParams.get("__auth") === "1";
  if (!enforceAuth && process.env.PLAYWRIGHT === "1" && process.env.PLAYWRIGHT_WEB_SERVER === "1") {
    return NextResponse.next();
  }

  if (hasValidSession(request)) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/auth/login";
  loginUrl.search = "";
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"]
};

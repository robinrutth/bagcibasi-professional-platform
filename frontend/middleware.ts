import { NextRequest, NextResponse } from "next/server";

import { getRoleFromJwt, hasPermission, type Role } from "@/lib/permissions";

const PUBLIC_PATHS = ["/login", "/unauthorized", "/_next", "/favicon.ico"];

const ROLE_PATHS: Array<{ prefix: string; allowedRoles?: Role[]; permission?: string }> = [
  { prefix: "/dashboard" },
  { prefix: "/customers", allowedRoles: ["admin", "manager"] },
  { prefix: "/reports", allowedRoles: ["admin", "manager", "viewer"] },
  { prefix: "/settings", allowedRoles: ["admin"], permission: "settings.read" },
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }
  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  if (!accessToken && !refreshToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  const rule = ROLE_PATHS.find((item) => pathname.startsWith(item.prefix));
  const role = getRoleFromJwt(accessToken);
  if (rule && !role && refreshToken) {
    return NextResponse.next();
  }
  if (rule?.allowedRoles && (!role || !rule.allowedRoles.includes(role))) {
    return NextResponse.redirect(new URL("/unauthorized", request.url));
  }
  if (rule?.permission && !hasPermission(role, rule.permission)) {
    return NextResponse.redirect(new URL("/unauthorized", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api).*)"],
};

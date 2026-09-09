import { NextResponse, type NextRequest } from "next/server";

const REFRESH_COOKIE = "taxla_refresh";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow Next.js internals, static assets, and API routes through unconditionally.
  if (
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/api/")
  ) {
    return NextResponse.next();
  }

  // Public customer requirement intake route - does not require employee login
  if (pathname.startsWith("/form")) {
    return NextResponse.next();
  }

  // Login page is public
  if (pathname === "/login") {
    return NextResponse.next();
  }

  // All CRM pages require the refresh cookie
  const hasRefresh = request.cookies.get(REFRESH_COOKIE);
  if (!hasRefresh) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    if (pathname !== "/") {
      url.searchParams.set("next", pathname);
    }
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|api|favicon.ico|.*\\.).*)"],
};
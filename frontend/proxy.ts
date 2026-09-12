import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "abgfc_session";

// Optimistic gate only: presence of the cookie. The API validates the signature on every
// request and the client redirects to /login on a 401.
export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const { pathname } = request.nextUrl;

  if (pathname === "/login") {
    return hasSession ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  }
  if (!hasSession) {
    const url = new URL("/login", request.url);
    if (pathname !== "/") url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|favicon.ico|icon.svg|manifest.webmanifest|.*\\.(?:png|svg|ico)).*)"],
};

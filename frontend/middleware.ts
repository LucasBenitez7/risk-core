import { type NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const hasToken = request.cookies.has("access_token");
  if (!hasToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!login|_next|favicon.ico|api).*)"],
};

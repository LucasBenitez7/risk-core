import { NextResponse, type NextRequest } from "next/server";

export async function POST() {
  return buildLogoutResponse();
}

export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const redirectTo = url.searchParams.get("redirect") ?? "/login";
  return buildLogoutResponse(redirectTo);
}

function buildLogoutResponse(redirectTo?: string) {
  if (redirectTo) {
    const res = NextResponse.redirect(new URL(redirectTo, "http://localhost:3001"));
    for (const name of ["access_token", "refresh_token", "username"]) {
      res.cookies.set(name, "", { path: "/", maxAge: 0 });
    }
    return res;
  }
  const res = NextResponse.json({ ok: true });
  for (const name of ["access_token", "refresh_token", "username"]) {
    res.cookies.set(name, "", { path: "/", maxAge: 0 });
  }
  return res;
}

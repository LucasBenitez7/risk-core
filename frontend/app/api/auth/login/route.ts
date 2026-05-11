import { NextResponse } from "next/server";

const GATEWAY_URL =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8080";

const ACCESS_COOKIE_MAX_AGE = 60 * 30; // 30 min — matches SimpleJWT ACCESS_TOKEN_LIFETIME
const REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24; // 24h
const USERNAME_COOKIE_MAX_AGE = 60 * 60 * 24;

export async function POST(request: Request) {
  const body = (await request.json()) as {
    username?: string;
    password?: string;
  };

  if (!body.username || !body.password) {
    return NextResponse.json(
      {
        error: {
          code: "BAD_REQUEST",
          message: "username and password required",
        },
      },
      { status: 400 },
    );
  }

  const upstream = await fetch(`${GATEWAY_URL}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    return NextResponse.json(
      {
        error: { code: "INVALID_CREDENTIALS", message: "Invalid credentials" },
      },
      { status: 401 },
    );
  }

  const tokens = (await upstream.json()) as { access: string; refresh: string };

  const res = NextResponse.json({ username: body.username });
  const isProd = process.env.NODE_ENV === "production";
  res.cookies.set("access_token", tokens.access, {
    httpOnly: true,
    sameSite: "lax",
    secure: isProd,
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE,
  });
  res.cookies.set("refresh_token", tokens.refresh, {
    httpOnly: true,
    sameSite: "lax",
    secure: isProd,
    path: "/",
    maxAge: REFRESH_COOKIE_MAX_AGE,
  });
  res.cookies.set("username", body.username, {
    httpOnly: false,
    sameSite: "lax",
    secure: isProd,
    path: "/",
    maxAge: USERNAME_COOKIE_MAX_AGE,
  });
  return res;
}

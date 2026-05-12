import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

const GATEWAY_URL =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8080";

async function handle(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  const search = request.nextUrl.search;
  let upstreamPath = request.nextUrl.pathname.replace(/^\/api\/proxy/, "/api");
  if (!upstreamPath.endsWith("/")) upstreamPath += "/";
  const upstreamUrl = `${GATEWAY_URL}${upstreamPath}${search}`;

  const headers: Record<string, string> = {};
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers["X-Request-ID"] = requestId;
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  const upstream = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
  });

  const responseBody = await upstream.text();
  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType)
    responseHeaders.set("content-type", upstreamContentType);

  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;

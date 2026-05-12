import { redirect } from "next/navigation";

const API_URL =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8080";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let code = "INTERNAL_ERROR";
  let message = `HTTP ${res.status}`;
  let details: Record<string, unknown> = {};
  try {
    const body = (await res.json()) as {
      error?: {
        code?: string;
        message?: string;
        details?: Record<string, unknown>;
      };
    };
    code = body.error?.code ?? code;
    message = body.error?.message ?? message;
    details = body.error?.details ?? {};
  } catch {
    /* non-JSON body */
  }
  return new ApiError(code, message, details);
}

/**
 * Client-side fetch. Hits the Next.js proxy Route Handler which reads the
 * httpOnly access_token cookie and injects the Bearer header before
 * forwarding to the gateway. The browser never touches the JWT.
 *
 * `path` must start with the gateway resource (e.g. "/policies/policies/").
 * Do NOT include "/api" — the proxy adds it.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const requestId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID": requestId,
    ...(options.headers as Record<string, string>),
  };

  const proxyPath = path.startsWith("/api/")
    ? path.replace("/api/", "/api/proxy/")
    : path;
  const res = await fetch(proxyPath, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    }
    throw new ApiError("UNAUTHORIZED", "Sesión expirada. Redirigiendo...");
  }

  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<T>;
}

/**
 * Server-side fetch for React Server Components. Reads the httpOnly
 * access_token cookie via next/headers and forwards directly to the
 * gateway as a Bearer header — no proxy round-trip.
 *
 * `path` must be a full gateway path (e.g. "/api/policies/metrics/").
 */
export async function serverFetch<T>(path: string): Promise<T> {
  const { cookies } = await import("next/headers");
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) redirect("/login");

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  const res = await fetch(`${API_URL}${path}`, {
    headers,
    cache: "no-store",
  });

  if (res.status === 401) {
    redirect("/api/auth/logout?redirect=/login");
  }

  if (!res.ok) throw await parseError(res);
  return res.json() as Promise<T>;
}

import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiFetch, ApiError } from "@/lib/api/client";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal("crypto", { randomUUID: () => "test-uuid" });
});

describe("apiFetch", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { hello: "world" }));
    const result = await apiFetch<{ hello: string }>("/api/test/");
    expect(result.hello).toBe("world");
  });

  it("rewrites /api/ paths to /api/proxy/", async () => {
    const fetchMock = mockFetch(200, {});
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/policies/policies/");
    const [calledPath] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(calledPath).toBe("/api/proxy/policies/policies/");
  });

  it("sets X-Request-ID header", async () => {
    const fetchMock = mockFetch(200, {});
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/test/");
    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((opts.headers as Record<string, string>)["X-Request-ID"]).toBe(
      "test-uuid",
    );
  });

  it("throws ApiError with UNAUTHORIZED code on 401", async () => {
    const logoutMock = mockFetch(200, {});
    const apiMock = mockFetch(401, {});
    vi.stubGlobal("fetch", (url: string, opts?: RequestInit) =>
      url === "/api/auth/logout" ? logoutMock(url, opts) : apiMock(url, opts),
    );
    vi.stubGlobal("window", { location: { href: "" } });
    await expect(apiFetch("/api/test/")).rejects.toMatchObject({
      name: "ApiError",
      code: "UNAUTHORIZED",
    });
  });

  it("throws ApiError with server error body on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(400, { error: { code: "BAD_REQUEST", message: "oops" } }),
    );
    const err = (await apiFetch("/api/test/").catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("BAD_REQUEST");
    expect(err.message).toBe("oops");
  });
});

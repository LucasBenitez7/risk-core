import { z } from "zod";
import { ApiError } from "@/lib/api/client";

const loginResponseSchema = z.object({ username: z.string() });
export type LoginResponse = z.infer<typeof loginResponseSchema>;

/**
 * Logs in via the Next.js Route Handler which sets the httpOnly cookies.
 * The JWT never reaches the browser's JS context.
 */
export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new ApiError("INVALID_CREDENTIALS", "Invalid credentials");
  }
  return loginResponseSchema.parse(await res.json());
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

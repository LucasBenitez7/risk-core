import { healthSchema } from "@/lib/api/schemas";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const SERVICES = [
  { name: "policy", path: "/health/policy/" },
  { name: "claims", path: "/health/claims/" },
  { name: "notifications", path: "/health/notifications/" },
  { name: "audit", path: "/health/audit/" },
] as const;

export type ServiceName = (typeof SERVICES)[number]["name"];

export interface ServiceHealth {
  name: ServiceName;
  status: "ok" | "error";
}

export async function getAllServiceHealth(): Promise<ServiceHealth[]> {
  return Promise.all(
    SERVICES.map(async ({ name, path }) => {
      try {
        const res = await fetch(`${API_URL}${path}`, {
          next: { revalidate: 10 },
        });
        const data = healthSchema.safeParse(await res.json());
        return {
          name,
          status: data.success && data.data.status === "ok" ? "ok" : "error",
        } satisfies ServiceHealth;
      } catch {
        return { name, status: "error" } satisfies ServiceHealth;
      }
    }),
  );
}

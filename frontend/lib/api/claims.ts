import { apiFetch, serverFetch } from "@/lib/api/client";
import {
  claimSchema,
  claimsMetricsSchema,
  paginatedSchema,
  type Claim,
  type ClaimsMetrics,
} from "@/lib/api/schemas";

export interface ListClaimsParams {
  status?: string;
  policy_id?: string;
  incident_type?: string;
  page?: number;
}

export async function listClaims(params: ListClaimsParams = {}) {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  ).toString();

  const data = await serverFetch<unknown>(
    `/api/claims/claims/${qs ? `?${qs}` : ""}`,
  );
  return paginatedSchema(claimSchema).parse(data);
}

export async function getClaim(id: string): Promise<Claim> {
  const data = await serverFetch<unknown>(`/api/claims/claims/${id}/`);
  return claimSchema.parse(data);
}

export async function transitionClaim(
  id: string,
  new_status: string,
  options: { notes?: string; approved_amount?: string } = {},
): Promise<Claim> {
  const data = await apiFetch<unknown>(`/api/claims/claims/${id}/transition/`, {
    method: "POST",
    body: JSON.stringify({ new_status, ...options }),
  });
  return claimSchema.parse(data);
}

export async function getClaimsMetrics(): Promise<ClaimsMetrics> {
  const data = await serverFetch<unknown>("/api/claims/metrics/");
  return claimsMetricsSchema.parse(data);
}

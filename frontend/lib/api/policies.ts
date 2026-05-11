import { apiFetch, serverFetch } from "@/lib/api/client";
import {
  paginatedSchema,
  policyMetricsSchema,
  policySchema,
  type Policy,
  type PolicyMetrics,
} from "@/lib/api/schemas";

export interface ListPoliciesParams {
  status?: string;
  policy_type?: string;
  customer_id?: string;
  page?: number;
  page_size?: number;
}

export async function listPolicies(params: ListPoliciesParams = {}) {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  ).toString();

  const data = await serverFetch<unknown>(
    `/api/policies/policies/${qs ? `?${qs}` : ""}`,
  );
  return paginatedSchema(policySchema).parse(data);
}

export async function getPolicy(id: string): Promise<Policy> {
  const data = await serverFetch<unknown>(`/api/policies/policies/${id}/`);
  return policySchema.parse(data);
}

export async function cancelPolicy(
  id: string,
  reason: string,
): Promise<Policy> {
  const data = await apiFetch<unknown>(`/api/policies/policies/${id}/cancel/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return policySchema.parse(data);
}

export async function getPolicyMetrics(): Promise<PolicyMetrics> {
  const data = await serverFetch<unknown>("/api/policies/metrics/");
  return policyMetricsSchema.parse(data);
}

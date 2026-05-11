import { serverFetch } from "@/lib/api/client";
import { auditEventSchema, cursorPaginatedSchema } from "@/lib/api/schemas";

export interface ListAuditParams {
  entity_type?: string;
  kafka_topic?: string;
  from_date?: string;
  to_date?: string;
  entity_id?: string;
  cursor?: string;
  page_size?: number;
}

export async function listAuditEvents(params: ListAuditParams = {}) {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  ).toString();

  const data = await serverFetch<unknown>(
    `/api/audit/events/${qs ? `?${qs}` : ""}`,
  );
  return cursorPaginatedSchema(auditEventSchema).parse(data);
}

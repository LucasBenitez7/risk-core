import { z } from "zod";

// ── Pagination ────────────────────────────────────────────────────────────────

export const paginatedSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    count: z.number(),
    next: z.string().url().nullable(),
    previous: z.string().url().nullable(),
    results: z.array(itemSchema),
  });

export const cursorPaginatedSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    next: z.string().nullable(),
    previous: z.string().nullable(),
    results: z.array(itemSchema),
  });

// ── Auth ──────────────────────────────────────────────────────────────────────

export const tokenSchema = z.object({
  access: z.string(),
  refresh: z.string(),
});

export type Token = z.infer<typeof tokenSchema>;

// ── Policy service ────────────────────────────────────────────────────────────

export const customerSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string(),
  email: z.string().email(),
  dni: z.string(),
  phone: z.string(),
  address: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type Customer = z.infer<typeof customerSchema>;

export const coverageSchema = z.object({
  id: z.string().uuid(),
  coverage_type: z.string(),
  coverage_amount: z.string(),
  description: z.string(),
});

export const policySchema = z.object({
  id: z.string().uuid(),
  policy_number: z.string(),
  customer_id: z.string().uuid().optional(),
  policy_type: z.enum(["LIFE", "HEALTH", "AUTO", "HOME", "BUSINESS"]),
  status: z.enum(["ACTIVE", "SUSPENDED", "CANCELLED", "EXPIRED"]),
  premium_amount: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  description: z.string(),
  cancellation_reason: z.string(),
  coverages: z.array(coverageSchema).optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type Policy = z.infer<typeof policySchema>;

export const policyMetricsSchema = z.object({
  active_policies: z.number(),
  policies_today: z.number(),
  policies_by_type: z.record(z.string(), z.number()),
  total_premium_active: z.string(),
});

export type PolicyMetrics = z.infer<typeof policyMetricsSchema>;

// ── Claims service ────────────────────────────────────────────────────────────

export const claimStatusHistorySchema = z.object({
  from_status: z.string().nullable(),
  to_status: z.string(),
  changed_at: z.string(),
  notes: z.string(),
});

export type ClaimStatusHistory = z.infer<typeof claimStatusHistorySchema>;

export const claimSchema = z.object({
  id: z.string().uuid(),
  claim_number: z.string(),
  policy_id: z.string().uuid(),
  claimant_name: z.string(),
  claimant_email: z.string().email(),
  incident_date: z.string(),
  incident_type: z.enum([
    "ACCIDENTE",
    "ROBO",
    "INCENDIO",
    "INUNDACION",
    "OTRO",
  ]),
  description: z.string().optional(),
  estimated_damage: z.string(),
  approved_amount: z.string().nullable().optional(),
  location: z.string().optional(),
  status: z.enum(["FILED", "UNDER_REVIEW", "APPROVED", "REJECTED", "RESOLVED"]),
  filed_at: z.string(),
  updated_at: z.string().optional(),
  status_history: z.array(claimStatusHistorySchema).optional(),
});

export type Claim = z.infer<typeof claimSchema>;

export const claimsMetricsSchema = z.object({
  open_claims: z.number(),
  claims_today: z.number(),
  claims_by_status: z.record(z.string(), z.number()),
  avg_resolution_days: z.number(),
});

export type ClaimsMetrics = z.infer<typeof claimsMetricsSchema>;

// ── Notifications service ─────────────────────────────────────────────────────

export const notificationSchema = z.object({
  id: z.string().uuid(),
  event_type: z.string(),
  recipient_email: z.string().email(),
  subject: z.string(),
  status: z.enum(["PENDING", "SENT", "FAILED"]),
  created_at: z.string(),
  sent_at: z.string().nullable(),
});

export type Notification = z.infer<typeof notificationSchema>;

export const notificationsMetricsSchema = z.object({
  sent_today: z.number(),
  failed_today: z.number(),
  pending: z.number(),
  success_rate_7d: z.number(),
});

export type NotificationsMetrics = z.infer<typeof notificationsMetricsSchema>;

// ── Audit service ─────────────────────────────────────────────────────────────

export const auditEventSchema = z.object({
  id: z.string().uuid(),
  event_id: z.string().uuid().optional(),
  event_type: z.string(),
  entity_type: z.string(),
  entity_id: z.string(),
  service: z.string().optional(),
  kafka_topic: z.string().optional(),
  payload: z.record(z.string(), z.unknown()).optional(),
  occurred_at: z.string(),
});

export type AuditEvent = z.infer<typeof auditEventSchema>;

// ── WebSocket ─────────────────────────────────────────────────────────────────

export const kafkaEventMessageSchema = z.object({
  id: z.string().uuid(),
  event_id: z.string().uuid(),
  event_type: z.string(),
  kafka_topic: z.string(),
  entity_type: z.string(),
  entity_id: z.string().uuid(),
  service: z.string(),
  occurred_at: z.string(),
  received_at: z.string(),
  payload: z.record(z.string(), z.unknown()),
});

export type KafkaEventMessage = z.infer<typeof kafkaEventMessageSchema>;

// ── Service health ────────────────────────────────────────────────────────────

export const healthSchema = z.object({
  status: z.string(),
  service: z.string().optional(),
  version: z.string().optional(),
  database: z.string().optional(),
});

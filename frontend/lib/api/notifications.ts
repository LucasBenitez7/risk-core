import { serverFetch } from "@/lib/api/client";
import {
  notificationsMetricsSchema,
  type NotificationsMetrics,
} from "@/lib/api/schemas";

export async function getNotificationsMetrics(): Promise<NotificationsMetrics> {
  const data = await serverFetch<unknown>("/api/notifications/metrics/");
  return notificationsMetricsSchema.parse(data);
}

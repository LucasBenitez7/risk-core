import { Suspense } from "react";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getPolicyMetrics } from "@/lib/api/policies";
import { getClaimsMetrics } from "@/lib/api/claims";
import { getNotificationsMetrics } from "@/lib/api/notifications";
import { getAllServiceHealth } from "@/lib/api/health";

async function MetricsSection() {
  const [policy, claims, notifications] = await Promise.all([
    getPolicyMetrics(),
    getClaimsMetrics(),
    getNotificationsMetrics(),
  ]);

  return (
    <section>
      <h2 className="mb-4 text-sm font-semibold tracking-wider text-slate-400 uppercase">
        Metrics
      </h2>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Active policies"
          value={policy.active_policies}
          hint={`${policy.policies_today} created today`}
        />
        <MetricCard
          label="Total premium"
          value={`$${policy.total_premium_active}`}
          hint="Active policies"
        />
        <MetricCard
          label="Open claims"
          value={claims.open_claims}
          hint={`${claims.claims_today} filed today`}
        />
        <MetricCard
          label="Avg resolution"
          value={`${claims.avg_resolution_days}d`}
          hint="Last 30 days"
        />
        <MetricCard
          label="Notifications sent"
          value={notifications.sent_today}
          hint="Today"
        />
        <MetricCard
          label="Failed notifications"
          value={notifications.failed_today}
          hint="Today"
        />
        <MetricCard
          label="Pending notifications"
          value={notifications.pending}
        />
        <MetricCard
          label="Success rate (7d)"
          value={`${notifications.success_rate_7d}%`}
        />
      </div>
    </section>
  );
}

async function HealthSection() {
  const services = await getAllServiceHealth();

  return (
    <section>
      <h2 className="mb-4 text-sm font-semibold tracking-wider text-slate-400 uppercase">
        Service health
      </h2>
      <div className="flex flex-wrap gap-3">
        {services.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2"
          >
            <span className="text-sm text-slate-300 capitalize">
              {svc.name}
            </span>
            <StatusBadge status={svc.status} />
          </div>
        ))}
      </div>
    </section>
  );
}

export default function OverviewPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">Overview</h1>
      <Suspense
        fallback={<div className="text-slate-500">Loading metrics…</div>}
      >
        <MetricsSection />
      </Suspense>
      <Suspense
        fallback={<div className="text-slate-500">Checking services…</div>}
      >
        <HealthSection />
      </Suspense>
    </div>
  );
}

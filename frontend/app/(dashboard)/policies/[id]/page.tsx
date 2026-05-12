import { notFound } from "next/navigation";
import Link from "next/link";
import { getPolicy } from "@/lib/api/policies";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { CancelPolicyButton } from "./CancelPolicyButton";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PolicyDetailPage({ params }: Props) {
  const { id } = await params;
  let policy;
  try {
    policy = await getPolicy(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/policies"
          className="text-sm text-slate-400 hover:text-white"
        >
          ← Policies
        </Link>
        <span className="text-slate-600">/</span>
        <span className="text-sm text-slate-300">{policy.policy_number}</span>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {policy.policy_number}
          </h1>
          <p className="mt-1 text-sm text-slate-400">{policy.policy_type}</p>
        </div>
        <StatusBadge status={policy.status.toLowerCase()} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900 p-5">
          <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Details
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Customer ID</dt>
              <dd className="font-mono text-slate-300">{policy.customer_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Premium</dt>
              <dd className="text-slate-300">${policy.premium_amount}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Start date</dt>
              <dd className="text-slate-300">{policy.start_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">End date</dt>
              <dd className="text-slate-300">{policy.end_date}</dd>
            </div>
            {policy.description && (
              <div className="pt-1">
                <dt className="mb-1 text-slate-400">Description</dt>
                <dd className="text-slate-300">{policy.description}</dd>
              </div>
            )}
            {policy.cancellation_reason && (
              <div className="pt-1">
                <dt className="mb-1 text-slate-400">Cancellation reason</dt>
                <dd className="text-red-400">{policy.cancellation_reason}</dd>
              </div>
            )}
          </dl>
        </div>

        {policy.coverages && policy.coverages.length > 0 && (
          <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900 p-5">
            <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
              Coverages
            </h2>
            <ul className="space-y-2">
              {policy.coverages.map((c) => (
                <li key={c.id} className="text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-300">{c.coverage_type}</span>
                    <span className="text-slate-400">${c.coverage_amount}</span>
                  </div>
                  {c.description && (
                    <p className="mt-0.5 text-xs text-slate-500">
                      {c.description}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {policy.status === "ACTIVE" && (
        <CancelPolicyButton policyId={policy.id} />
      )}
    </div>
  );
}

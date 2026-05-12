import { notFound } from "next/navigation";
import Link from "next/link";
import { getClaim } from "@/lib/api/claims";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TransitionClaimButton } from "./TransitionClaimButton";

interface Props {
  params: Promise<{ id: string }>;
}

const TRANSITIONS: Record<string, string[]> = {
  FILED: ["UNDER_REVIEW"],
  UNDER_REVIEW: ["APPROVED", "REJECTED"],
  APPROVED: ["RESOLVED"],
  REJECTED: [],
  RESOLVED: [],
};

export default async function ClaimDetailPage({ params }: Props) {
  const { id } = await params;
  let claim;
  try {
    claim = await getClaim(id);
  } catch {
    notFound();
  }

  const nextStatuses = TRANSITIONS[claim.status] ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/claims"
          className="text-sm text-slate-400 hover:text-white"
        >
          ← Claims
        </Link>
        <span className="text-slate-600">/</span>
        <span className="text-sm text-slate-300">{claim.claim_number}</span>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {claim.claim_number}
          </h1>
          <p className="mt-1 text-sm text-slate-400">{claim.incident_type}</p>
        </div>
        <StatusBadge status={claim.status.toLowerCase()} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900 p-5">
          <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
            Details
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Claimant</dt>
              <dd className="text-slate-300">{claim.claimant_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Email</dt>
              <dd className="text-slate-300">{claim.claimant_email}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Policy ID</dt>
              <dd className="font-mono text-xs text-slate-300">
                {claim.policy_id}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Incident date</dt>
              <dd className="text-slate-300">{claim.incident_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Filed at</dt>
              <dd className="text-slate-300">{claim.filed_at}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Location</dt>
              <dd className="text-slate-300">{claim.location}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Estimated damage</dt>
              <dd className="text-slate-300">${claim.estimated_damage}</dd>
            </div>
            {claim.approved_amount && (
              <div className="flex justify-between">
                <dt className="text-slate-400">Approved amount</dt>
                <dd className="text-emerald-400">${claim.approved_amount}</dd>
              </div>
            )}
            {claim.description && (
              <div className="pt-1">
                <dt className="mb-1 text-slate-400">Description</dt>
                <dd className="text-slate-300">{claim.description}</dd>
              </div>
            )}
          </dl>
        </div>

        {claim.status_history && claim.status_history.length > 0 && (
          <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900 p-5">
            <h2 className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
              Status history
            </h2>
            <ul className="space-y-2">
              {claim.status_history.map((h, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <div className="mt-1 h-1.5 w-1.5 flex shrink-0 rounded-full bg-slate-500" />
                  <div>
                    <span className="text-slate-400">
                      {h.from_status ?? "—"} → {h.to_status}
                    </span>
                    <p className="text-xs text-slate-500">{h.changed_at}</p>
                    {h.notes && (
                      <p className="mt-0.5 text-xs text-slate-400">{h.notes}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {nextStatuses.length > 0 && (
        <TransitionClaimButton
          claimId={claim.id}
          nextStatuses={nextStatuses}
          currentStatus={claim.status}
        />
      )}
    </div>
  );
}

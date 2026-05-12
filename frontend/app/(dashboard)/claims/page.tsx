import Link from "next/link";
import { listClaims } from "@/lib/api/claims";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface Props {
  searchParams: Promise<{ status?: string; page?: string }>;
}

export default async function ClaimsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Number(sp.page ?? 1);
  const {
    results: claims,
    count,
    next,
    previous,
  } = await listClaims({
    status: sp.status,
    page,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Claims</h1>
        <span className="text-sm text-slate-400">{count} total</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-700">
        <table className="w-full text-sm">
          <thead className="bg-slate-800">
            <tr>
              {[
                "Number",
                "Claimant",
                "Incident",
                "Type",
                "Damage",
                "Status",
                "",
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold tracking-wider text-slate-400 uppercase"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700 bg-slate-900">
            {claims.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-slate-500"
                >
                  No claims found
                </td>
              </tr>
            )}
            {claims.map((claim) => (
              <tr
                key={claim.id}
                className="transition-colors hover:bg-slate-800/50"
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-300">
                  {claim.claim_number}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  {claim.claimant_name}
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {claim.incident_date}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  {claim.incident_type}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  ${claim.estimated_damage}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={claim.status.toLowerCase()} />
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/claims/${claim.id}`}
                    className="text-indigo-400 transition-colors hover:text-indigo-300"
                  >
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <Link
          href={previous ? `?page=${page - 1}` : "#"}
          className={`text-sm ${previous ? "text-indigo-400 hover:text-indigo-300" : "pointer-events-none text-slate-600"}`}
        >
          ← Previous
        </Link>
        <span className="text-sm text-slate-400">Page {page}</span>
        <Link
          href={next ? `?page=${page + 1}` : "#"}
          className={`text-sm ${next ? "text-indigo-400 hover:text-indigo-300" : "pointer-events-none text-slate-600"}`}
        >
          Next →
        </Link>
      </div>
    </div>
  );
}

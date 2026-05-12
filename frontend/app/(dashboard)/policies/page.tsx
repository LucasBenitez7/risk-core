import Link from "next/link";
import { listPolicies } from "@/lib/api/policies";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface Props {
  searchParams: Promise<{
    status?: string;
    policy_type?: string;
    page?: string;
  }>;
}

export default async function PoliciesPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Number(sp.page ?? 1);
  const {
    results: policies,
    count,
    next,
    previous,
  } = await listPolicies({
    status: sp.status,
    policy_type: sp.policy_type,
    page,
    page_size: 20,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Policies</h1>
        <span className="text-sm text-slate-400">{count} total</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-700">
        <table className="w-full text-sm">
          <thead className="bg-slate-800">
            <tr>
              {[
                "Number",
                "Customer",
                "Type",
                "Premium",
                "Status",
                "Start",
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
            {policies.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-slate-500"
                >
                  No policies found
                </td>
              </tr>
            )}
            {policies.map((policy) => (
              <tr
                key={policy.id}
                className="transition-colors hover:bg-slate-800/50"
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-300">
                  {policy.policy_number}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  {policy.policy_number}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  {policy.policy_type}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  ${policy.premium_amount}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={policy.status.toLowerCase()} />
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {policy.start_date}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/policies/${policy.id}`}
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

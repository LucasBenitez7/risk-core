import Link from "next/link";
import { listAuditEvents } from "@/lib/api/audit";

interface Props {
  searchParams: Promise<{ cursor?: string; entity_type?: string }>;
}

function extractCursor(link: string): string {
  try {
    const url = new URL(link);
    return url.searchParams.get("cursor") ?? "";
  } catch {
    return "";
  }
}

export default async function AuditPage({ searchParams }: Props) {
  const sp = await searchParams;
  const { results, next, previous } = await listAuditEvents({
    cursor: sp.cursor,
    entity_type: sp.entity_type,
    page_size: 25,
  });

  const nextCursor = next ? extractCursor(next) : "";
  const prevCursor = previous ? extractCursor(previous) : "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Audit log</h1>

      <div className="overflow-hidden rounded-xl border border-slate-700">
        <table className="w-full text-sm">
          <thead className="bg-slate-800">
            <tr>
              {[
                "Event type",
                "Entity",
                "Entity ID",
                "Topic",
                "Occurred at",
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
            {results.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-slate-500"
                >
                  No audit events found
                </td>
              </tr>
            )}
            {results.map((event) => (
              <tr
                key={event.id}
                className="transition-colors hover:bg-slate-800/50"
              >
                <td className="px-4 py-3 text-slate-300">{event.event_type}</td>
                <td className="px-4 py-3 text-slate-400">
                  {event.entity_type}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">
                  {event.entity_id.slice(0, 12)}…
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {event.service ?? event.kafka_topic}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {event.occurred_at}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <Link
          href={prevCursor ? `?cursor=${encodeURIComponent(prevCursor)}` : "#"}
          className={`text-sm ${prevCursor ? "text-indigo-400 hover:text-indigo-300" : "pointer-events-none text-slate-600"}`}
        >
          ← Newer
        </Link>
        <Link
          href={nextCursor ? `?cursor=${encodeURIComponent(nextCursor)}` : "#"}
          className={`text-sm ${nextCursor ? "text-indigo-400 hover:text-indigo-300" : "pointer-events-none text-slate-600"}`}
        >
          Older →
        </Link>
      </div>
    </div>
  );
}

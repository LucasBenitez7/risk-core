"use client";

import { useEventsStore } from "@/lib/stores/eventsStore";
import { useEventStream } from "@/lib/hooks/useEventStream";
import type { ConnectionState } from "@/lib/hooks/useEventStream";

const STATE_BADGE: Record<ConnectionState, { label: string; cls: string }> = {
  idle: { label: "Idle", cls: "bg-slate-700 text-slate-400" },
  connecting: { label: "Connecting…", cls: "bg-yellow-900/50 text-yellow-400" },
  open: { label: "Live", cls: "bg-emerald-900/50 text-emerald-400" },
  closed: { label: "Reconnecting…", cls: "bg-orange-900/50 text-orange-400" },
};

export function EventFeed() {
  const events = useEventsStore((s) => s.events);
  const clear = useEventsStore((s) => s.clear);
  const { connState } = useEventStream();

  const badge = STATE_BADGE[connState];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.cls}`}
        >
          {connState === "open" && (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          )}
          {badge.label}
        </span>
        {events.length > 0 && (
          <button
            onClick={clear}
            className="text-xs text-slate-500 transition-colors hover:text-slate-300"
          >
            Clear ({events.length})
          </button>
        )}
      </div>

      <div className="max-h-[600px] space-y-2 overflow-y-auto pr-1">
        {events.length === 0 && (
          <p className="py-12 text-center text-sm text-slate-500">
            Waiting for events…
          </p>
        )}
        {events.map((evt, i) => (
          <div
            key={i}
            className="rounded-lg border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
          >
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold text-indigo-400">
                {evt.event_type}
              </span>
              <span className="text-slate-500">{evt.service}</span>
            </div>
            <div className="mb-1 text-slate-500">{evt.occurred_at}</div>
            <pre className="break-all whitespace-pre-wrap text-slate-300">
              {JSON.stringify(evt.payload, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

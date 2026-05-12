type Status = string;

const STATUS_STYLES: Record<string, string> = {
  active: "bg-emerald-900/50 text-emerald-400",
  cancelled: "bg-slate-700 text-slate-400",
  expired: "bg-slate-700 text-slate-400",
  open: "bg-blue-900/50 text-blue-400",
  under_review: "bg-yellow-900/50 text-yellow-400",
  approved: "bg-emerald-900/50 text-emerald-400",
  resolved: "bg-slate-700 text-slate-400",
  rejected: "bg-red-900/50 text-red-400",
  sent: "bg-emerald-900/50 text-emerald-400",
  failed: "bg-red-900/50 text-red-400",
  pending: "bg-yellow-900/50 text-yellow-400",
  ok: "bg-emerald-900/50 text-emerald-400",
  error: "bg-red-900/50 text-red-400",
};

const DEFAULT_STYLE = "bg-slate-700 text-slate-300";

interface StatusBadgeProps {
  status: Status;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const style = STATUS_STYLES[status.toLowerCase()] ?? DEFAULT_STYLE;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

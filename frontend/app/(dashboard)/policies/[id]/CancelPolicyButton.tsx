"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { cancelPolicy } from "@/lib/api/policies";

interface Props {
  policyId: string;
}

export function CancelPolicyButton({ policyId }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleCancel() {
    if (!reason.trim()) {
      toast.error("Cancellation reason is required");
      return;
    }
    setLoading(true);
    try {
      await cancelPolicy(policyId, reason.trim());
      toast.success("Policy cancelled");
      setOpen(false);
      router.refresh();
    } catch {
      toast.error("Failed to cancel policy");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-md border border-red-700 px-4 py-2 text-sm text-red-400 transition-colors hover:bg-red-900/30"
      >
        Cancel policy
      </button>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-red-800 bg-red-950/30 p-5">
      <h3 className="text-sm font-semibold text-red-400">Cancel policy</h3>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for cancellation…"
        rows={3}
        className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-red-500 focus:ring-1 focus:ring-red-500 focus:outline-none"
      />
      <div className="flex gap-2">
        <button
          onClick={handleCancel}
          disabled={loading}
          className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-60"
        >
          {loading ? "Cancelling…" : "Confirm"}
        </button>
        <button
          onClick={() => {
            setOpen(false);
            setReason("");
          }}
          className="rounded-md px-4 py-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

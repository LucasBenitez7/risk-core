"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { transitionClaim } from "@/lib/api/claims";

interface Props {
  claimId: string;
  currentStatus: string;
  nextStatuses: string[];
}

export function TransitionClaimButton({
  claimId,
  currentStatus,
  nextStatuses,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState(nextStatuses[0] ?? "");
  const [notes, setNotes] = useState("");
  const [approvedAmount, setApprovedAmount] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleTransition() {
    setLoading(true);
    try {
      await transitionClaim(claimId, selectedStatus, {
        notes: notes.trim() || undefined,
        approved_amount: approvedAmount.trim() || undefined,
      });
      toast.success(`Claim moved to ${selectedStatus}`);
      setOpen(false);
      router.refresh();
    } catch {
      toast.error("Failed to transition claim");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
      >
        Transition status
      </button>
    );
  }

  return (
    <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-5">
      <h3 className="text-sm font-semibold text-white">
        Transition from {currentStatus}
      </h3>

      <div>
        <label className="mb-1.5 block text-xs text-slate-400">
          New status
        </label>
        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
          className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
        >
          {nextStatuses.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {selectedStatus === "APPROVED" && (
        <div>
          <label className="mb-1.5 block text-xs text-slate-400">
            Approved amount
          </label>
          <input
            type="number"
            value={approvedAmount}
            onChange={(e) => setApprovedAmount(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
          />
        </div>
      )}

      <div>
        <label className="mb-1.5 block text-xs text-slate-400">
          Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleTransition}
          disabled={loading}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-60"
        >
          {loading ? "Saving…" : "Confirm"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="rounded-md px-4 py-2 text-sm text-slate-400 transition-colors hover:text-white"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

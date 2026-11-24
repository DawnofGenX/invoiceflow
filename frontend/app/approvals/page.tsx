"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  type ApprovalRequest,
  type InvoiceSummary,
} from "@/lib/api";
import { fmtDateTime, fmtMoney } from "@/lib/format";
import StatusBadge from "@/components/StatusBadge";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [invoices, setInvoices] = useState<Record<string, InvoiceSummary>>({});
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [apprs, invs] = await Promise.all([
        api.listApprovals(),
        api.listInvoices(),
      ]);
      setApprovals(apprs);
      setInvoices(Object.fromEntries(invs.map((i) => [i.id, i])));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: string, decision: "approve" | "reject") {
    setActing(id);
    try {
      await api.decide(id, decision);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setActing(null);
    }
  }

  const pending = approvals.filter((a) => a.status === "pending");
  const resolved = approvals.filter((a) => a.status !== "pending");

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
          Approval queue
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Invoices routed for human review — the agent explains why it did not
          auto-approve.
        </p>
      </div>

      {pending.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 p-10 text-center text-sm text-zinc-500">
          No pending approvals. Invoices under $500 auto-approve; larger or
          new-vendor invoices appear here.
        </div>
      ) : (
        <ul className="space-y-4">
          {pending.map((a) => {
            const inv = invoices[a.invoice_id];
            return (
              <li
                key={a.id}
                className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400 ring-1 ring-inset ring-amber-500/30">
                    <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-12a.75.75 0 0 0-1.5 0v4a.75.75 0 0 0 .3.6l2.25 1.75a.75.75 0 1 0 .9-1.2l-1.95-1.52V6Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <div>
                    <Link
                      href={`/invoices/${a.invoice_id}`}
                      className="text-sm font-semibold text-zinc-100 hover:text-emerald-400"
                    >
                      {inv?.vendor_name ?? "Unknown vendor"}
                    </Link>
                    <p className="text-xs text-zinc-500">
                      {inv
                        ? `${inv.invoice_number} · ${fmtMoney(inv.amount, inv.currency)}`
                        : a.invoice_id}{" "}
                      · {fmtDateTime(a.created_at)}
                    </p>
                    {a.reason && (
                      <p className="mt-1 text-xs text-amber-400/90">{a.reason}</p>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => decide(a.id, "reject")}
                    disabled={acting === a.id}
                    className="rounded-lg border border-red-500/40 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-50"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => decide(a.id, "approve")}
                    disabled={acting === a.id}
                    className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400 disabled:opacity-50"
                  >
                    Approve
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {resolved.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold text-zinc-200">
            Resolved
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/30">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-3 font-medium">Invoice</th>
                  <th className="px-4 py-3 font-medium">Decision</th>
                  <th className="px-4 py-3 font-medium">Resolved</th>
                </tr>
              </thead>
              <tbody>
                {resolved.map((a) => {
                  const inv = invoices[a.invoice_id];
                  return (
                    <tr
                      key={a.id}
                      className="border-b border-zinc-800/60 last:border-0"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/invoices/${a.invoice_id}`}
                          className="font-medium text-zinc-200 hover:text-emerald-400"
                        >
                          {inv?.vendor_name ?? a.invoice_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={a.status} />
                      </td>
                      <td className="px-4 py-3 text-zinc-500">
                        {fmtDateTime(a.resolved_at ?? a.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

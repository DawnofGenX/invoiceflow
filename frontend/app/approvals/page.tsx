"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type ApprovalRequest, type InvoiceSummary } from "@/lib/api";
import { fmtMoney, fmtStamp, shortRef } from "@/lib/format";
import { StatusToken, Lamp } from "@/components/StatusToken";

export default function HeldPage() {
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
      window.dispatchEvent(new Event("invoiceflow:changed"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setActing(null);
    }
  }

  const pending = approvals.filter((a) => a.status === "pending");
  const resolved = approvals.filter((a) => a.status !== "pending");

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em]">
            Held for review
          </h1>
          <p className="mt-1 max-w-[66ch] text-[13px] text-ink-mute">
            Every invoice here carries the sentence that stopped it. Read the
            reason, then stamp it through or void it — the decision is printed
            into the same record the agents wrote.
          </p>
        </div>
        <div className="flex items-center gap-2 border border-rule-firm bg-slip px-3 py-1.5">
          <Lamp live={pending.length > 0} />
          <span className="micro !text-ink">
            <span className="num">{pending.length}</span> awaiting decision
          </span>
        </div>
      </div>

      {error && (
        <div className="mt-5 border border-void/40 bg-void-soft px-4 py-3">
          <p className="num text-[11.5px] text-void">{error}</p>
        </div>
      )}

      {pending.length === 0 ? (
        <div className="mt-6 border border-rule bg-print-2/50 px-5 py-8">
          <p className="micro">No entries on hold</p>
          <p className="mt-2 max-w-[62ch] text-[12.5px] text-ink-mute">
            Invoices under $500 settle automatically. Anything larger, any new
            vendor, and anything flagged by validation is stopped here and
            printed with its reason.
          </p>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {pending.map((a) => {
            const inv = invoices[a.invoice_id];
            const busy = acting === a.id;
            return (
              <li key={a.id} className="border border-rule-firm bg-slip">
                <div className="flex flex-wrap items-center gap-3 border-b border-rule px-4 py-2">
                  <span className="micro !text-ink">
                    Held · <span className="num">{shortRef(a.invoice_id)}</span>
                  </span>
                  <span className="num text-[10.5px] text-ink-mute">
                    raised {fmtStamp(a.created_at)}
                  </span>
                  <span className="ml-auto">
                    <StatusToken status={inv?.status ?? "awaiting_approval"} />
                  </span>
                </div>

                <div className="grid gap-4 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                  <div className="min-w-0">
                    <Link
                      href={`/invoices/${a.invoice_id}`}
                      className="text-[15px] font-semibold text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                    >
                      {inv?.vendor_name || "Vendor unread"}
                    </Link>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-ink-mute">
                      <span className="num">
                        {inv?.invoice_number || "no number"}
                      </span>
                      {inv?.po_number && (
                        <span className="num">{inv.po_number}</span>
                      )}
                      {inv && (
                        <span className="num">
                          conf {Math.round((inv.confidence_score ?? 0) * 100)}%
                        </span>
                      )}
                    </div>

                    <div className="mt-3 border-y border-rule py-2">
                      <p className="micro">Reason for hold</p>
                      <p className="mt-1 max-w-[68ch] text-[12.5px] leading-[1.55] text-ink">
                        {a.reason || "Routed for human review."}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-3 sm:min-w-[190px]">
                    <span className="num text-[18px] leading-none text-ink">
                      {inv ? fmtMoney(inv.amount, inv.currency) : "—"}
                    </span>
                    <div className="flex w-full gap-2 sm:w-auto">
                      <button
                        onClick={() => decide(a.id, "reject")}
                        disabled={busy}
                        className="flex-1 border border-void/50 px-3 py-2 text-[10.5px] font-medium uppercase tracking-[0.1em] text-void transition-colors duration-150 hover:bg-void-soft disabled:cursor-not-allowed disabled:opacity-40 sm:flex-none"
                      >
                        Void
                      </button>
                      <button
                        onClick={() => decide(a.id, "approve")}
                        disabled={busy}
                        className="flex-1 rounded-[3px] bg-ink px-4 py-2 text-[10.5px] font-medium uppercase tracking-[0.1em] text-print transition-colors duration-150 hover:bg-ink-soft disabled:cursor-not-allowed disabled:opacity-40 sm:flex-none"
                      >
                        {busy ? "Stamping…" : "Approve"}
                      </button>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {resolved.length > 0 && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between border-b border-ink pb-1.5">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.1em] text-ink">
              Resolved
            </h2>
            <span className="num text-[10.5px] text-ink-mute">
              {resolved.length} entries
            </span>
          </div>
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">
              Approvals already decided, with who decided and when
            </caption>
            <thead>
              <tr className="border-b border-rule">
                {["Ref", "Vendor", "Disposition", "Decision", "Resolved"].map(
                  (h) => (
                    <th
                      key={h}
                      className="micro py-1.5 pr-3 text-left font-normal last:pr-0"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {resolved.map((a) => {
                const inv = invoices[a.invoice_id];
                return (
                  <tr
                    key={a.id}
                    className="border-b border-rule last:border-0 hover:bg-print-2/60"
                  >
                    <td className="num py-1.5 pr-3 text-[11px] text-ink-mute">
                      {shortRef(a.invoice_id)}
                    </td>
                    <td className="py-1.5 pr-3 text-[12px]">
                      <Link
                        href={`/invoices/${a.invoice_id}`}
                        className="text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                      >
                        {inv?.vendor_name || "Vendor unread"}
                      </Link>
                    </td>
                    <td className="py-1.5 pr-3">
                      <StatusToken status={inv?.status ?? a.status} />
                    </td>
                    <td className="py-1.5 pr-3 text-[11.5px] uppercase tracking-[0.06em] text-ink-mute">
                      {a.status}
                    </td>
                    <td className="num py-1.5 text-[11px] text-ink-mute">
                      {fmtStamp(a.resolved_at ?? a.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

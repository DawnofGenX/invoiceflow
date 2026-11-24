"use client";

import Link from "next/link";
import StatusBadge from "./StatusBadge";
import { fmtConfidence, fmtDate, fmtMoney } from "@/lib/format";
import type { InvoiceSummary } from "@/lib/api";

export default function InvoiceTable({
  invoices,
}: {
  invoices: InvoiceSummary[];
}) {
  if (invoices.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-800 p-10 text-center text-sm text-zinc-500">
        No invoices yet. Upload one to see the agents work.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/30">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500">
            <th className="px-4 py-3 font-medium">Invoice</th>
            <th className="px-4 py-3 font-medium">Vendor</th>
            <th className="px-4 py-3 font-medium">Amount</th>
            <th className="px-4 py-3 font-medium">PO</th>
            <th className="px-4 py-3 font-medium">Confidence</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Received</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr
              key={inv.id}
              className="border-b border-zinc-800/60 last:border-0 hover:bg-zinc-800/30"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/invoices/${inv.id}`}
                  className="font-medium text-zinc-200 hover:text-emerald-400"
                >
                  {inv.invoice_number}
                </Link>
              </td>
              <td className="px-4 py-3 text-zinc-300">{inv.vendor_name}</td>
              <td className="px-4 py-3 font-medium text-zinc-200">
                {fmtMoney(inv.amount, inv.currency)}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-zinc-400">
                {inv.po_number || "—"}
              </td>
              <td className="px-4 py-3 text-zinc-400">
                {fmtConfidence(inv.confidence_score)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={inv.status} />
              </td>
              <td className="px-4 py-3 text-zinc-500">
                {fmtDate(inv.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

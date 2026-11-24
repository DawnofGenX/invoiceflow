"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type InvoiceDetail as InvoiceDetailType } from "@/lib/api";
import {
  fmtConfidence,
  fmtDate,
  fmtDateTime,
  fmtMoney,
} from "@/lib/format";
import StatusBadge from "@/components/StatusBadge";
import AuditTimeline from "@/components/AuditTimeline";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wider text-zinc-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-zinc-200">{value}</dd>
    </div>
  );
}

export default function InvoiceDetail({ id }: { id: string }) {
  const [invoice, setInvoice] = useState<InvoiceDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getInvoice(id)
      .then(setInvoice)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="py-20 text-center text-sm text-zinc-500">Loading…</div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              {invoice.invoice_number}
            </h1>
            <StatusBadge status={invoice.status} />
          </div>
          <p className="mt-1 text-sm text-zinc-400">
            {invoice.vendor_name}
            {invoice.vendor_email && (
              <span className="text-zinc-500"> · {invoice.vendor_email}</span>
            )}
          </p>
        </div>
        <Link
          href="/"
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          ← Back
        </Link>
      </div>

      <dl className="grid grid-cols-2 gap-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 sm:grid-cols-4">
        <Field
          label="Amount"
          value={
            <span className="text-lg font-semibold text-zinc-100">
              {fmtMoney(invoice.amount, invoice.currency)}
            </span>
          }
        />
        <Field label="PO number" value={invoice.po_number || "—"} />
        <Field label="Invoice date" value={fmtDate(invoice.invoice_date)} />
        <Field label="Due date" value={fmtDate(invoice.due_date)} />
        <Field label="Confidence" value={fmtConfidence(invoice.confidence_score)} />
        <Field label="Tax" value={invoice.tax_amount ?? "—"} />
        <Field label="Received" value={fmtDateTime(invoice.created_at)} />
        <Field label="Currency" value={invoice.currency} />
      </dl>

      {invoice.line_items.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold text-zinc-200">
            Line items
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/30">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-3 font-medium">Description</th>
                  <th className="px-4 py-3 font-medium">Qty</th>
                  <th className="px-4 py-3 font-medium">Unit price</th>
                  <th className="px-4 py-3 font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {invoice.line_items.map((li) => (
                  <tr
                    key={li.id}
                    className="border-b border-zinc-800/60 last:border-0"
                  >
                    <td className="px-4 py-3 text-zinc-300">
                      {li.description}
                      {li.matched_po_line_id && (
                        <span className="ml-2 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-400">
                          PO-matched
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{li.quantity}</td>
                    <td className="px-4 py-3 text-zinc-400">
                      {fmtMoney(li.unit_price, invoice.currency)}
                    </td>
                    <td className="px-4 py-3 font-medium text-zinc-200">
                      {fmtMoney(li.total, invoice.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-200">
          Audit trail{" "}
          <span className="text-sm font-normal text-zinc-500">
            — why every decision was made
          </span>
        </h2>
        <div className="flex gap-2">
          <a
            href={api.exportUrl(id, "json")}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-800"
          >
            Export JSON
          </a>
          <a
            href={api.exportUrl(id, "pdf")}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-800"
          >
            Export PDF
          </a>
        </div>
      </div>

      <AuditTimeline entries={invoice.audit_entries} />

      {invoice.raw_text && (
        <details className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <summary className="cursor-pointer text-sm font-medium text-zinc-300">
            Raw extracted text
          </summary>
          <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs text-zinc-500">
            {invoice.raw_text}
          </pre>
        </details>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type InvoiceDetail as InvoiceDetailType } from "@/lib/api";
import {
  fmtConfidence,
  fmtDate,
  fmtMoney,
  fmtStamp,
  shortRef,
} from "@/lib/format";
import { StatusToken } from "@/components/StatusToken";
import ConfirmationSlip, { DecisionLine } from "@/components/ConfirmationSlip";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="micro self-center py-1.5">{label}</dt>
      <dd className="border-b border-rule py-1.5 pr-2 text-[12px] text-ink">
        {value}
      </dd>
    </>
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
      <div className="mx-auto max-w-[1080px] px-5 py-8 sm:px-8">
        <div className="border border-void/40 bg-void-soft px-4 py-3">
          <p className="num text-[11.5px] text-void">{error}</p>
        </div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="mx-auto max-w-[1080px] px-5 py-8 sm:px-8">
        <div className="h-3 w-40 bg-print-2" />
        <div className="mt-4 space-y-1.5">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-6 border-b border-rule bg-print-2/40" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1080px] px-5 py-8 sm:px-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href="/"
          className="micro !text-ink-mute underline decoration-rule-firm underline-offset-4 hover:!text-ink hover:decoration-ink"
        >
          ← Register
        </Link>
        <div className="flex items-center gap-2">
          <a
            href={api.exportUrl(id, "json")}
            className="border border-rule-firm px-2.5 py-1 font-mono text-[10.5px] text-ink-mute transition-colors duration-150 hover:border-ink hover:text-ink"
          >
            export json
          </a>
          <a
            href={api.exportUrl(id, "pdf")}
            className="border border-rule-firm px-2.5 py-1 font-mono text-[10.5px] text-ink-mute transition-colors duration-150 hover:border-ink hover:text-ink"
          >
            export pdf
          </a>
        </div>
      </div>

      <ConfirmationSlip
        reference={invoice.invoice_number || shortRef(invoice.id)}
        status={invoice.status}
        vendor={invoice.vendor_name}
        amount={invoice.amount}
        currency={invoice.currency}
        po={invoice.po_number}
        confidence={invoice.confidence_score}
        received={invoice.created_at}
        entries={[]}
        footer={
          invoice.vendor_email ? (
            <span className="num">{invoice.vendor_email}</span>
          ) : undefined
        }
        bare
      />

      <div className="mt-4 border border-rule-firm bg-slip px-4 py-3">
        <div className="flex items-baseline justify-between border-b border-ink pb-1.5">
          <span className="micro !text-ink">Record</span>
          <span className="num text-[10.5px] text-ink-mute">
            {fmtStamp(invoice.created_at)}
          </span>
        </div>
        <dl className="grid grid-cols-[112px_minmax(0,1fr)_112px_minmax(0,1fr)] gap-x-4">
          <Field
            label="Amount"
            value={
              <span className="num text-[14px] text-ink">
                {fmtMoney(invoice.amount, invoice.currency)}
              </span>
            }
          />
          <Field label="PO number" value={invoice.po_number || "—"} />
          <Field label="Invoice date" value={fmtDate(invoice.invoice_date)} />
          <Field label="Due date" value={fmtDate(invoice.due_date)} />
          <Field label="Confidence" value={fmtConfidence(invoice.confidence_score)} />
          <Field
            label="Tax"
            value={invoice.tax_amount != null ? `$${invoice.tax_amount}` : "—"}
          />
          <Field label="Currency" value={invoice.currency} />
          <Field label="Source" value={invoice.file_path ? "uploaded file" : "—"} />
        </dl>
      </div>

      {invoice.line_items.length > 0 && (
        <section className="mt-6">
          <div className="flex items-baseline justify-between border-b border-ink pb-1.5">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.1em]">
              Line items
            </h2>
            <span className="num text-[10.5px] text-ink-mute">
              {invoice.line_items.length} line
              {invoice.line_items.length === 1 ? "" : "s"}
            </span>
          </div>
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">
              Invoice line items as extracted, with purchase-order match state
            </caption>
            <thead>
              <tr className="border-b border-rule">
                {["Description", "Qty", "Unit", "Total", "Match"].map((h) => (
                  <th
                    key={h}
                    className="micro py-1.5 pr-3 text-left font-normal last:pr-0"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invoice.line_items.map((li) => (
                <tr key={li.id} className="border-b border-rule last:border-0">
                  <td className="py-1.5 pr-3 text-[12px] text-ink">
                    {li.description}
                  </td>
                  <td className="num py-1.5 pr-3 text-[11.5px] text-ink-mute">
                    {li.quantity}
                  </td>
                  <td className="num py-1.5 pr-3 text-[11.5px] text-ink-mute">
                    {fmtMoney(li.unit_price, invoice.currency)}
                  </td>
                  <td className="num py-1.5 pr-3 text-[12px] text-ink">
                    {fmtMoney(li.total, invoice.currency)}
                  </td>
                  <td className="py-1.5">
                    {li.matched_po_line_id ? (
                      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-settled">
                        po-matched
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-mute">
                        unmatched
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="mt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink pb-1.5">
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.1em]">
            Decision lines
          </h2>
          <span className="num text-[10.5px] text-ink-mute">
            {invoice.audit_entries.length} printed · why each step resolved the
            way it did
          </span>
        </div>
        {invoice.audit_entries.length === 0 ? (
          <p className="border-b border-rule py-4 text-[12px] text-ink-mute">
            No decision lines recorded for this entry yet.
          </p>
        ) : (
          <ol className="divide-y divide-rule">
            {invoice.audit_entries.map((entry, i) => (
              <DecisionLine key={entry.id} entry={entry} index={i} />
            ))}
          </ol>
        )}
      </section>

      {invoice.raw_text && (
        <details className="mt-6 border border-rule bg-print-2/40">
          <summary className="cursor-pointer px-4 py-2 text-[10.5px] font-medium uppercase tracking-[0.1em] text-ink-mute hover:text-ink">
            Raw text as read from the document
          </summary>
          <pre className="max-h-72 overflow-auto border-t border-rule px-4 py-3 font-mono text-[11px] leading-[1.6] whitespace-pre-wrap text-ink-mute">
            {invoice.raw_text}
          </pre>
        </details>
      )}

      <div className="mt-6 flex items-center gap-2 border-t border-rule pt-3">
        <StatusToken status={invoice.status} />
        <span className="text-[11px] text-ink-mute">
          Every line above is served from the audit table — nothing in this view
          is reconstructed after the fact.
        </span>
      </div>
    </div>
  );
}

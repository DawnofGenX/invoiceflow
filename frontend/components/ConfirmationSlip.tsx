import type { ReactNode } from "react";
import type { AuditEntry } from "@/lib/api";
import {
  agentLabel,
  fmtConfidence,
  fmtMoney,
  fmtStamp,
  shortRef,
} from "@/lib/format";
import { StatusToken } from "@/components/StatusToken";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="micro self-center">{label}</dt>
      <dd className="text-[12.5px]">{children}</dd>
    </>
  );
}

/** One printed confirmation line: agent, action, rule, confidence, reasoning. */
export function DecisionLine({
  entry,
  index,
  href,
  fresh,
}: {
  entry: AuditEntry;
  index: number;
  href?: string;
  fresh?: boolean;
}) {
  const parts = (
    <>
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className="num text-[10px] text-ink-mute">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink">
          {agentLabel(entry.agent_name)}
        </span>
        <span className="num text-[10.5px] text-ink-mute">{entry.action}</span>
        {entry.rule_fired && (
          <span className="num rounded-[2px] border border-rule-firm px-1.5 py-[1px] text-[10px] text-ink">
            {entry.rule_fired}
          </span>
        )}
        <span className="num ml-auto whitespace-nowrap text-[10.5px] text-ink-mute">
          {fmtConfidence(entry.confidence)} · {entry.duration_ms} ms
        </span>
      </div>
      <p className="mt-1.5 max-w-[68ch] text-[12.5px] leading-[1.55] text-ink-soft">
        {entry.reasoning || "—"}
      </p>
    </>
  );

  return (
    <li
      className={`border-b border-rule px-4 py-2.5 last:border-0 ${
        fresh ? "printed" : ""
      }`}
    >
      {href ? (
        <a
          href={href}
          className="block transition-colors duration-150 hover:bg-print-2/70"
        >
          {parts}
        </a>
      ) : (
        parts
      )}
    </li>
  );
}

/**
 * The confirmation slip: a fixed-cell record of one invoice. Fields are ruled,
 * lines are printed in the order the agents ran, in place.
 */
export default function ConfirmationSlip({
  reference,
  status,
  vendor,
  amount,
  currency = "USD",
  po,
  confidence,
  received,
  entries,
  footer,
  emptyNote = "No decisions printed for this record yet.",
  bare = false,
}: {
  reference: string;
  status: string;
  vendor?: string | null;
  amount?: number | null;
  currency?: string;
  po?: string | null;
  confidence?: number | null;
  received?: string;
  entries: AuditEntry[];
  footer?: ReactNode;
  emptyNote?: string;
  /** Header + fields only — the caller prints the decision lines itself. */
  bare?: boolean;
}) {
  return (
    <article className="flex min-w-0 flex-col border border-rule-firm bg-slip">
      <header className="flex items-start justify-between gap-3 border-b border-ink px-4 py-3">
        <div className="min-w-0">
          <p className="micro">Confirmation</p>
          <h2 className="num mt-1 truncate text-[15px] font-medium text-ink">
            {reference}
          </h2>
        </div>
        <StatusToken status={status} />
      </header>

      <dl className="fieldgrid px-4 py-2">
        <Field label="Issued">{<span className="num">{received ? fmtStamp(received) : "—"}</span>}</Field>
        <Field label="Vendor">{vendor || "unread"}</Field>
        <Field label="Amount">
          <span className="num">
            {amount == null ? "—" : fmtMoney(amount, currency)}
          </span>
        </Field>
        <Field label="PO">
          <span className="num">{po || "none"}</span>
        </Field>
        <Field label="Confidence">
          <span className="num">{fmtConfidence(confidence ?? null)}</span>
        </Field>
      </dl>

      {!bare && (
        <>
          <div className="flex items-baseline justify-between border-t border-rule bg-print-2/60 px-4 py-1.5">
            <span className="micro">Decision lines</span>
            <span className="num text-[10.5px] text-ink-mute">
              {entries.length} printed
            </span>
          </div>

          {entries.length === 0 ? (
            <p className="px-4 py-6 text-[12.5px] text-ink-mute">{emptyNote}</p>
          ) : (
            <ol>
              {entries.map((e, i) => (
                <DecisionLine key={e.id ?? i} entry={e} index={i} />
              ))}
            </ol>
          )}
        </>
      )}

      {footer && (
        <div className="mt-auto border-t border-rule px-4 py-2.5">{footer}</div>
      )}
    </article>
  );
}

/** Stable reference for a record: invoice number when read, else a short id. */
export function slipReference(invoiceNumber?: string | null, id?: string) {
  if (invoiceNumber) return invoiceNumber;
  if (id) return shortRef(id);
  return "UNREAD";
}

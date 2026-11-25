"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type AuditSummary, type VendorRow } from "@/lib/api";
import {
  agentLabel,
  fmtConfidence,
  fmtDateTime,
  fmtMoney,
  fmtStamp,
  shortRef,
} from "@/lib/format";

function LedgerCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 px-4 py-2.5">
      <p className="micro">{label}</p>
      <p className="num mt-1 text-[16px] leading-none text-ink">{value}</p>
    </div>
  );
}

function Bar({
  label,
  count,
  max,
  sub,
}: {
  label: string;
  count: number;
  max: number;
  sub?: string;
}) {
  const pct = max > 0 ? Math.max((count / max) * 100, 2) : 0;
  return (
    <div className="grid grid-cols-[minmax(120px,180px)_minmax(0,1fr)_40px] items-center gap-3 border-b border-rule px-4 py-[7px] last:border-0">
      <span className="num truncate text-[11.5px] text-ink" title={label}>
        {label}
      </span>
      <span
        className="flex h-[6px] items-center"
        role="presentation"
        aria-hidden="true"
      >
        <span className="h-[6px] w-full max-w-full bg-rule/70">
          <span
            className="block h-[6px] bg-ink/75"
            style={{ width: `${pct}%` }}
          />
        </span>
      </span>
      <span className="num text-right text-[11.5px] text-ink-mute">
        {count}
        {sub ? <span className="ml-1 text-[10px]">{sub}</span> : null}
      </span>
    </div>
  );
}

export default function EvidencePage() {
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [vendors, setVendors] = useState<VendorRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, v] = await Promise.all([api.auditSummary(), api.vendors()]);
      setSummary(s);
      setVendors(v);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8">
        <div className="border border-void/40 bg-void-soft p-5">
          <p className="text-[12.5px] font-medium text-void">
            The evidence ledger could not be read.
          </p>
          <pre className="num mt-2 whitespace-pre-wrap text-[11px] text-void/90">
            {error}
          </pre>
        </div>
      </div>
    );
  }

  const maxRule = Math.max(1, ...(summary?.rules_fired.map((r) => r.count) ?? [0]));
  const maxAgent = Math.max(1, ...Object.values(summary?.by_agent ?? { x: 0 }));

  return (
    <div className="mx-auto max-w-[1440px] px-5 sm:px-8">
      <div className="pt-6">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em]">
          Evidence
        </h1>
        <p className="mt-1 max-w-[66ch] text-[13px] text-ink-mute">
          The whole decision record, across every invoice: what was decided, which
          rule fired, and how sure the agent was. This is the part other AP tools
          leave out.
        </p>
      </div>

      <div className="mt-5 grid grid-cols-2 divide-x divide-rule border-y border-rule sm:grid-cols-3 lg:grid-cols-5">
        <LedgerCell
          label="Decisions"
          value={summary ? String(summary.total_decisions) : "—"}
        />
        <LedgerCell
          label="Per invoice"
          value={summary ? summary.decisions_per_invoice.toFixed(1) : "—"}
        />
        <LedgerCell
          label="Automation"
          value={
            summary ? `${Math.round(summary.automation_rate * 100)}%` : "—"
          }
        />
        <LedgerCell
          label="Avg confidence"
          value={fmtConfidence(summary?.avg_confidence ?? null)}
        />
        <LedgerCell
          label="Low confidence"
          value={summary ? String(summary.low_confidence_count) : "—"}
        />
      </div>
      {summary && (
        <p className="num mt-1.5 text-[10.5px] text-ink-mute">
          {summary.automated_invoices} of {summary.total_invoices} invoices went
          straight through · {summary.human_review_invoices} reached a human ·
          low confidence means below{" "}
          {Math.round(summary.low_confidence_threshold * 100)}%
        </p>
      )}

      <div className="mt-7 grid gap-5 lg:grid-cols-2">
        <section className="self-start border border-rule-firm bg-slip">
          <header className="border-b border-ink px-4 py-2.5">
            <h2 className="text-[12.5px] font-semibold text-ink">
              Rules that fired
            </h2>
            <p className="mt-0.5 text-[11px] text-ink-mute">
              The control behind each decision, counted.
            </p>
          </header>
          <div>
            {(summary?.rules_fired ?? []).map((r) => (
              <Bar key={r.rule} label={r.rule} count={r.count} max={maxRule} />
            ))}
            {summary && summary.rules_fired.length === 0 && (
              <p className="px-4 py-6 text-[12px] text-ink-mute">
                No rule has fired yet. Send an invoice through intake.
              </p>
            )}
          </div>
        </section>

        <section className="self-start border border-rule-firm bg-slip">
          <header className="border-b border-ink px-4 py-2.5">
            <h2 className="text-[12.5px] font-semibold text-ink">
              Decisions by agent
            </h2>
            <p className="mt-0.5 text-[11px] text-ink-mute">
              Where the work actually happens in the pipeline.
            </p>
          </header>
          <div>
            {Object.entries(summary?.by_agent ?? {}).map(([agent, count]) => (
              <Bar
                key={agent}
                label={agentLabel(agent)}
                count={count}
                max={maxAgent}
              />
            ))}
          </div>
        </section>
      </div>

      <section className="mt-6 border border-rule-firm bg-slip">
        <header className="flex items-baseline justify-between border-b border-ink px-4 py-2.5">
          <div>
            <h2 className="text-[12.5px] font-semibold text-ink">
              Recent decisions
            </h2>
            <p className="mt-0.5 text-[11px] text-ink-mute">
              Newest first, verbatim. Every line is a printed cell in its
              invoice&apos;s record.
            </p>
          </div>
          <span className="num text-[10.5px] text-ink-mute">
            {summary?.recent.length ?? 0} shown
          </span>
        </header>
        <ol>
          {(summary?.recent ?? []).map((d) => (
            <li
              key={d.id}
              className="border-b border-rule px-4 py-2.5 last:border-0"
            >
              <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                <span className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-ink">
                  {agentLabel(d.agent)}
                </span>
                <span className="num text-[10.5px] text-ink-mute">{d.action}</span>
                {d.rule_fired && (
                  <span className="num rounded-[2px] border border-rule-firm px-1.5 py-[1px] text-[10px] text-ink">
                    {d.rule_fired}
                  </span>
                )}
                <span className="num ml-auto whitespace-nowrap text-[10.5px] text-ink-mute">
                  {fmtConfidence(d.confidence)} · {d.duration_ms} ms ·{" "}
                  {fmtDateTime(d.created_at)}
                </span>
              </div>
              <p className="mt-1.5 max-w-[86ch] text-[12.5px] leading-[1.55] text-ink-soft">
                {d.reasoning}
              </p>
              <p className="mt-1 text-[10.5px] text-ink-mute">
                <Link
                  href={`/invoices/${d.invoice_id}`}
                  className="num text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                >
                  {d.invoice_number || shortRef(d.invoice_id)}
                </Link>
                {" · "}
                {d.vendor_name || "unknown vendor"}
              </p>
            </li>
          ))}
          {summary && summary.recent.length === 0 && (
            <li className="px-4 py-8 text-center text-[12.5px] text-ink-mute">
              Nothing recorded yet — intake an invoice to start the record.
            </li>
          )}
        </ol>
      </section>

      <section className="mt-6 border border-rule-firm bg-slip">
        <header className="border-b border-ink px-4 py-2.5">
          <h2 className="text-[12.5px] font-semibold text-ink">Vendors</h2>
          <p className="mt-0.5 text-[11px] text-ink-mute">
            A supplier with no settled history is exactly what forces manual
            verification.
          </p>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className="micro px-4 py-2 font-medium">
                  Vendor
                </th>
                <th scope="col" className="micro px-4 py-2 text-right font-medium">
                  Invoices
                </th>
                <th scope="col" className="micro px-4 py-2 text-right font-medium">
                  Settled
                </th>
                <th scope="col" className="micro px-4 py-2 text-right font-medium">
                  Value
                </th>
                <th scope="col" className="micro px-4 py-2 text-right font-medium">
                  Last seen
                </th>
                <th scope="col" className="micro px-4 py-2 font-medium">
                  History
                </th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.vendor_name} className="border-b border-rule last:border-0">
                  <td className="px-4 py-[7px] text-[12.5px] text-ink">
                    {v.vendor_name}
                  </td>
                  <td className="num px-4 py-[7px] text-right text-[11.5px] text-ink-mute">
                    {v.invoice_count}
                  </td>
                  <td className="num px-4 py-[7px] text-right text-[11.5px] text-ink-mute">
                    {v.settled_count}
                  </td>
                  <td className="num px-4 py-[7px] text-right text-[11.5px] text-ink">
                    {fmtMoney(v.total_amount)}
                  </td>
                  <td className="num px-4 py-[7px] text-right text-[11px] text-ink-mute">
                    {v.last_seen ? fmtStamp(v.last_seen) : "—"}
                  </td>
                  <td className="px-4 py-[7px]">
                    <span
                      className={`num inline-flex items-center gap-1.5 rounded-[2px] border px-1.5 py-[2px] text-[10px] uppercase ${
                        v.has_history
                          ? "border-settled/40 bg-settled-soft text-settled"
                          : "border-hold/40 bg-hold-soft text-hold"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className={`h-[5px] w-[5px] ${
                          v.has_history ? "bg-settled" : "bg-hold"
                        }`}
                      />
                      {v.has_history ? "established" : "new — verify"}
                    </span>
                  </td>
                </tr>
              ))}
              {vendors.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[12.5px] text-ink-mute">
                    No vendors on the book yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

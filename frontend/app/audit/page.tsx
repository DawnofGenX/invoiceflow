"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type AuditSummary, type VendorRow } from "@/lib/api";
import {
  agentLabel,
  fmtConfidence,
  fmtDateTime,
  fmtMoney,
} from "@/lib/format";
import StatCard from "@/components/StatCard";

function RuleChip({ rule }: { rule: string | null }) {
  if (!rule) return <span className="text-xs text-zinc-600">—</span>;
  return (
    <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] text-emerald-300 ring-1 ring-inset ring-emerald-500/25">
      {rule}
    </span>
  );
}

function Bar({
  label,
  count,
  max,
  tone = "emerald",
}: {
  label: string;
  count: number;
  max: number;
  tone?: "emerald" | "blue";
}) {
  const pct = max > 0 ? Math.max((count / max) * 100, 3) : 0;
  const fill = tone === "blue" ? "bg-blue-500/70" : "bg-emerald-500/70";
  return (
    <div className="flex items-center gap-3">
      <span className="w-44 shrink-0 truncate font-mono text-xs text-zinc-400" title={label}>
        {label}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full rounded-full ${fill}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right text-xs tabular-nums text-zinc-400">
        {count}
      </span>
    </div>
  );
}

export default function TransparencyPage() {
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
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
        Failed to load the transparency report.
        <pre className="mt-2 whitespace-pre-wrap text-xs text-red-400">{error}</pre>
      </div>
    );
  }

  const maxRule = Math.max(1, ...(summary?.rules_fired.map((r) => r.count) ?? [0]));
  const maxAgent = Math.max(1, ...Object.values(summary?.by_agent ?? { x: 0 }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
          Transparency report
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Every agent decision across the whole ledger — what was decided, how
          confident it was, and which rule made the call.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Decisions logged"
          value={summary?.total_decisions ?? "—"}
          hint={
            summary ? `${summary.decisions_per_invoice} per invoice` : undefined
          }
        />
        <StatCard
          label="Automation rate"
          value={
            summary ? `${Math.round(summary.automation_rate * 100)}%` : "—"
          }
          tone="emerald"
          hint={
            summary
              ? `${summary.automated_invoices} of ${summary.total_invoices} straight through`
              : undefined
          }
        />
        <StatCard
          label="Avg confidence"
          value={fmtConfidence(summary?.avg_confidence ?? null)}
          tone="blue"
          hint="across every recorded decision"
        />
        <StatCard
          label="Low confidence"
          value={summary?.low_confidence_count ?? "—"}
          tone="amber"
          hint={
            summary
              ? `below ${Math.round(summary.low_confidence_threshold * 100)}% · flagged for humans`
              : undefined
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h2 className="text-sm font-semibold text-zinc-200">Rules that fired</h2>
          <p className="mt-1 text-xs text-zinc-500">
            The exact control behind each decision. This is the part other AP tools
            don&apos;t record.
          </p>
          <div className="mt-4 space-y-2.5">
            {(summary?.rules_fired ?? []).map((r) => (
              <Bar key={r.rule} label={r.rule} count={r.count} max={maxRule} />
            ))}
            {summary && summary.rules_fired.length === 0 && (
              <p className="text-xs text-zinc-500">No rules have fired yet.</p>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h2 className="text-sm font-semibold text-zinc-200">Decisions by agent</h2>
          <p className="mt-1 text-xs text-zinc-500">
            How much of the pipeline each agent owns.
          </p>
          <div className="mt-4 space-y-2.5">
            {Object.entries(summary?.by_agent ?? {}).map(([agent, count]) => (
              <Bar
                key={agent}
                label={agentLabel(agent)}
                count={count}
                max={maxAgent}
                tone="blue"
              />
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50">
        <div className="border-b border-zinc-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-200">Recent decisions</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Newest first. Each row is one audit entry, verbatim.
          </p>
        </div>
        <ul className="divide-y divide-zinc-800/70">
          {(summary?.recent ?? []).map((d) => (
            <li key={d.id} className="px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[11px] font-medium text-zinc-300">
                  {agentLabel(d.agent)}
                </span>
                <span className="font-mono text-[11px] text-zinc-500">{d.action}</span>
                <RuleChip rule={d.rule_fired} />
                <span className="ml-auto flex items-center gap-2 text-[11px] text-zinc-500">
                  <span className="tabular-nums">{fmtConfidence(d.confidence)}</span>
                  <span>{d.duration_ms} ms</span>
                  <span>{fmtDateTime(d.created_at)}</span>
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-zinc-300">{d.reasoning}</p>
              <p className="mt-1.5 text-xs text-zinc-500">
                <Link
                  href={`/invoices/${d.invoice_id}`}
                  className="text-emerald-400 hover:underline"
                >
                  {d.invoice_number || "invoice"}
                </Link>{" "}
                · {d.vendor_name || "unknown vendor"}
              </p>
            </li>
          ))}
          {summary && summary.recent.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-zinc-500">
              Nothing recorded yet — upload an invoice.
            </li>
          )}
        </ul>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50">
        <div className="border-b border-zinc-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-200">Vendors</h2>
          <p className="mt-1 text-xs text-zinc-500">
            A supplier with no settled history is what forces manual verification.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500">
                <th className="px-5 py-3 font-medium">Vendor</th>
                <th className="px-5 py-3 font-medium">Invoices</th>
                <th className="px-5 py-3 font-medium">Settled</th>
                <th className="px-5 py-3 font-medium">Total value</th>
                <th className="px-5 py-3 font-medium">History</th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v) => (
                <tr
                  key={v.vendor_name}
                  className="border-b border-zinc-800/60 last:border-0 hover:bg-zinc-800/30"
                >
                  <td className="px-5 py-3 text-zinc-200">{v.vendor_name}</td>
                  <td className="px-5 py-3 tabular-nums text-zinc-400">
                    {v.invoice_count}
                  </td>
                  <td className="px-5 py-3 tabular-nums text-zinc-400">
                    {v.settled_count}
                  </td>
                  <td className="px-5 py-3 font-medium text-zinc-200">
                    {fmtMoney(v.total_amount)}
                  </td>
                  <td className="px-5 py-3">
                    {v.has_history ? (
                      <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300 ring-1 ring-inset ring-emerald-500/25">
                        established
                      </span>
                    ) : (
                      <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300 ring-1 ring-inset ring-amber-500/25">
                        new — verify
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {vendors.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-sm text-zinc-500">
                    No vendors yet.
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

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  api,
  type AuditEntry,
  type DashboardStats,
  type InvoiceDetail,
  type InvoiceSummary,
} from "@/lib/api";
import { fmtMoney, fmtStamp, statusLabel } from "@/lib/format";
import RegisterTable from "@/components/RegisterTable";
import PipelineRoute from "@/components/PipelineRoute";
import ConfirmationSlip, { slipReference } from "@/components/ConfirmationSlip";

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="micro">{label}</span>
      <span className="num text-[11.5px] text-ink">{value}</span>
    </span>
  );
}

export default function RegisterPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<InvoiceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [changed, setChanged] = useState<Set<string>>(new Set());
  const [seeding, setSeeding] = useState(false);
  const prevStatus = useRef<Map<string, string>>(new Map());

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return invoices.filter((inv) => {
      const matchesStatus =
        statusFilter === "all" || inv.status === statusFilter;
      if (!matchesStatus) return false;
      if (!needle) return true;
      return [inv.invoice_number, inv.vendor_name, inv.po_number ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [invoices, query, statusFilter]);

  const statusOptions = useMemo(() => {
    const seen = new Set(invoices.map((i) => i.status));
    return ["all", ...Array.from(seen).sort()];
  }, [invoices]);

  const load = useCallback(async () => {
    try {
      const [s, invs] = await Promise.all([api.dashboard(), api.listInvoices()]);
      setStats(s);
      setInvoices(invs);
      setError(null);

      // Rows whose disposition moved since the last read hold a lamp.
      const moved = new Set<string>();
      invs.forEach((inv) => {
        const before = prevStatus.current.get(inv.id);
        if (before && before !== inv.status) moved.add(inv.id);
        prevStatus.current.set(inv.id, inv.status);
      });
      if (moved.size > 0) setChanged(moved);

      setSelectedId((cur) => cur ?? invs[0]?.id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let live = true;
    setDetailLoading(true);
    api
      .getInvoice(selectedId)
      .then((d) => {
        if (live) setDetail(d);
      })
      .catch(() => {
        if (live) setDetail(null);
      })
      .finally(() => {
        if (live) setDetailLoading(false);
      });
    return () => {
      live = false;
    };
  }, [selectedId]);

  function select(id: string) {
    setSelectedId(id);
    setChanged((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await api.seed();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSeeding(false);
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[1440px] px-5 py-10 sm:px-8">
        <div className="border border-void/40 bg-void-soft p-5">
          <p className="text-[12.5px] font-medium text-void">
            The register could not be read — the API did not answer.
          </p>
          <pre className="num mt-2 whitespace-pre-wrap text-[11px] text-void/90">
            {error}
          </pre>
        </div>
      </div>
    );
  }

  const settled =
    (stats?.by_status.paid ?? 0) +
    (stats?.by_status.payment_scheduled ?? 0) +
    (stats?.by_status.approved ?? 0);
  const held =
    (stats?.by_status.awaiting_approval ?? 0) +
    (stats?.by_status.needs_review ?? 0);
  const voided = stats?.by_status.rejected ?? 0;
  const newest = invoices[0]?.created_at;

  const entries: AuditEntry[] = detail?.audit_entries ?? [];

  return (
    <div className="mx-auto max-w-[1440px] px-5 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-3 pt-6">
        <div className="min-w-0">
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em]">
            Register
          </h1>
          <p className="mt-1 max-w-[64ch] text-[13px] text-ink-mute">
            Every invoice on the book. Open a row to read its confirmation lines:
            what each agent decided, how sure it was, and which rule made the
            call.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="rounded-[3px] border border-rule-firm px-3 py-2 text-[10.5px] font-medium uppercase tracking-[0.1em] text-ink transition-colors duration-150 hover:bg-print-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {seeding ? "Seeding…" : "Seed demo ledger"}
          </button>
          <Link
            href="/upload"
            className="rounded-[3px] bg-ink px-3 py-2 text-[10.5px] font-medium uppercase tracking-[0.1em] text-print transition-colors duration-150 hover:bg-ink-soft"
          >
            Intake an invoice
          </Link>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-y border-rule py-2.5">
        <PipelineRoute
          received={stats?.total_invoices ?? 0}
          settled={settled}
          held={held}
          voided={voided}
        />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Meta label="On book" value={stats ? fmtMoney(stats.total_amount) : "—"} />
          {newest && <Meta label="Last entry" value={fmtStamp(newest)} />}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 py-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-2">
            <div className="flex flex-wrap items-center gap-2">
              <label className="sr-only" htmlFor="register-search">
                Search the register
              </label>
              <input
                id="register-search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Reference, vendor or PO"
                className="w-52 border border-field bg-slip px-2.5 py-1.5 text-[12.5px] text-ink placeholder:text-ink-mute focus:border-ink focus:outline-none"
              />
              <label className="sr-only" htmlFor="register-status">
                Filter by disposition
              </label>
              <select
                id="register-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="border border-field bg-slip px-2 py-1.5 text-[12px] text-ink focus:border-ink focus:outline-none"
              >
                {statusOptions.map((s) => (
                  <option key={s} value={s}>
                    {s === "all" ? "All dispositions" : statusLabel(s)}
                  </option>
                ))}
              </select>
            </div>
            <p className="num text-[10.5px] text-ink-mute">
              {visible.length} of {invoices.length} rows
            </p>
          </div>

          <div className="border border-rule-firm bg-slip">
            <RegisterTable
              rows={visible}
              selectedId={selectedId}
              onSelect={select}
              changedIds={changed}
            />
          </div>

          <p className="mt-2 text-[11px] text-ink-mute">
            A lit lamp means a row changed since you last read it. Opening the
            row clears it.
          </p>
        </div>

        <aside className="self-start lg:sticky lg:top-[68px]">
          {detail ? (
            <ConfirmationSlip
              reference={slipReference(
                detail.invoice_number,
                detail.id,
              )}
              status={detail.status}
              vendor={detail.vendor_name}
              amount={detail.amount}
              currency={detail.currency}
              po={detail.po_number}
              confidence={detail.confidence_score}
              received={detail.created_at}
              entries={entries}
              footer={
                <div className="flex items-center justify-between gap-3">
                  <span className="micro">
                    {detail.line_items.length} line items
                  </span>
                  <Link
                    href={`/invoices/${detail.id}`}
                    className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink underline decoration-rule-firm underline-offset-4 hover:decoration-ink"
                  >
                    Open full record
                  </Link>
                </div>
              }
            />
          ) : (
            <div className="border border-rule-firm bg-slip px-4 py-6">
              <p className="micro">Confirmation</p>
              <p className="mt-2 text-[12.5px] text-ink-mute">
                {detailLoading
                  ? "Reading the record…"
                  : "Select a row in the register to read its confirmation slip."}
              </p>
            </div>
          )}

          <div className="mt-3 border border-rule bg-print-2/60 px-4 py-3">
            <p className="micro">How a decision is printed</p>
            <p className="mt-1.5 text-[11.5px] leading-[1.55] text-ink-mute">
              Intake reads the document type, extraction pulls the fields, five
              validation rules run in order, and routing stamps a disposition.
              Each step writes one line — the reasoning, the confidence, and the
              rule that fired.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

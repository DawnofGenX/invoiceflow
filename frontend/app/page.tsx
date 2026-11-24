"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type DashboardStats, type InvoiceSummary } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import StatCard from "@/components/StatCard";
import InvoiceTable from "@/components/InvoiceTable";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, invs] = await Promise.all([
        api.dashboard(),
        api.listInvoices(),
      ]);
      setStats(s);
      setInvoices(invs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSeed() {
    setSeeding(true);
    try {
      await api.seed();
      await load();
    } finally {
      setSeeding(false);
    }
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
        Failed to reach the backend API. Is it running on port 8000?
        <pre className="mt-2 whitespace-pre-wrap text-xs text-red-400">{error}</pre>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            Accounts Payable
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Every decision below is made by an agent — and every agent explains
            itself.
          </p>
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 disabled:opacity-50"
        >
          {seeding ? "Seeding…" : "Seed demo data"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total invoices" value={stats?.total_invoices ?? "—"} />
        <StatCard
          label="Auto-approved"
          value={stats?.auto_approved ?? "—"}
          tone="emerald"
          hint="paid without human review"
        />
        <StatCard
          label="Awaiting approval"
          value={stats?.pending_approvals ?? "—"}
          tone="amber"
        />
        <StatCard
          label="Needs review"
          value={stats?.needs_review ?? "—"}
          tone="orange"
        />
        <StatCard
          label="Total value"
          value={stats ? fmtMoney(stats.total_amount) : "—"}
          tone="blue"
        />
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-200">Recent invoices</h2>
        <Link
          href="/upload"
          className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-emerald-400"
        >
          + Upload invoice
        </Link>
      </div>

      <InvoiceTable invoices={invoices} />
    </div>
  );
}

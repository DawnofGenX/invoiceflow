"use client";

import type { InvoiceSummary } from "@/lib/api";
import { ageLabel, fmtConfidence, fmtMoney, shortRef } from "@/lib/format";
import { Lamp, StatusToken } from "@/components/StatusToken";

export default function RegisterTable({
  rows,
  selectedId,
  onSelect,
  changedIds,
  emptyNote = "Nothing in the register yet. Send an invoice through intake.",
}: {
  rows: InvoiceSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  changedIds: Set<string>;
  emptyNote?: string;
}) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[680px] border-collapse text-left">
        <caption className="sr-only">
          Invoice register — one row per invoice, with the disposition stamped by
          the approval agent
        </caption>
        <thead>
          <tr className="border-b border-ink">
            <th scope="col" className="w-6 px-2 py-2" />
            <th scope="col" className="micro px-2 py-2 font-medium">
              Reference
            </th>
            <th scope="col" className="micro px-2 py-2 font-medium">
              Vendor
            </th>
            <th scope="col" className="micro px-2 py-2 text-right font-medium">
              Amount
            </th>
            <th scope="col" className="micro px-2 py-2 font-medium">
              PO
            </th>
            <th scope="col" className="micro px-2 py-2 text-right font-medium">
              Conf
            </th>
            <th scope="col" className="micro px-2 py-2 font-medium">
              Disposition
            </th>
            <th scope="col" className="micro px-2 py-2 text-right font-medium">
              Age
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((inv) => {
            const selected = inv.id === selectedId;
            const changed = changedIds.has(inv.id);
            return (
              <tr
                key={inv.id}
                tabIndex={0}
                aria-selected={selected}
                onClick={() => onSelect(inv.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(inv.id);
                  }
                }}
                className={`cursor-pointer border-b border-rule transition-colors duration-150 ${
                  selected
                    ? "bg-ink text-print"
                    : "hover:bg-print-2/80 focus-visible:bg-print-2/80"
                }`}
              >
                <td className="px-2 py-0">
                  <Lamp live={changed && !selected} invert={selected} />
                </td>
                <td
                  className={`num px-2 py-[7px] text-[11.5px] ${
                    selected ? "text-print" : "text-ink"
                  }`}
                >
                  {inv.invoice_number || shortRef(inv.id)}
                </td>
                <td
                  className={`max-w-[220px] truncate px-2 py-[7px] text-[12.5px] ${
                    selected ? "text-print" : inv.vendor_name ? "text-ink" : "text-ink-mute"
                  }`}
                >
                  {inv.vendor_name || "unread document"}
                </td>
                <td
                  className={`num px-2 py-[7px] text-right text-[12px] ${
                    selected ? "text-print" : "text-ink"
                  }`}
                >
                  {fmtMoney(inv.amount, inv.currency)}
                </td>
                <td
                  className={`num px-2 py-[7px] text-[11px] ${
                    selected ? "text-print/80" : "text-ink-mute"
                  }`}
                >
                  {inv.po_number || "—"}
                </td>
                <td
                  className={`num px-2 py-[7px] text-right text-[11.5px] ${
                    selected ? "text-print/80" : "text-ink-mute"
                  }`}
                >
                  {fmtConfidence(inv.confidence_score)}
                </td>
                <td className="px-2 py-[6px]">
                  <StatusToken status={inv.status} invert={selected} />
                </td>
                <td
                  className={`num px-2 py-[7px] text-right text-[11px] ${
                    selected ? "text-print/80" : "text-ink-mute"
                  }`}
                >
                  {ageLabel(inv.created_at)}
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="px-2 py-10 text-center">
                <p className="text-[12.5px] text-ink-mute">{emptyNote}</p>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

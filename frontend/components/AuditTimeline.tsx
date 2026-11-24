"use client";

import {
  agentLabel,
  fmtConfidence,
  fmtDateTime,
} from "@/lib/format";
import type { AuditEntry } from "@/lib/api";

const agentTones: Record<string, string> = {
  intake: "text-sky-400 ring-sky-500/30 bg-sky-500/10",
  extraction: "text-violet-400 ring-violet-500/30 bg-violet-500/10",
  validation: "text-blue-400 ring-blue-500/30 bg-blue-500/10",
  approval: "text-amber-400 ring-amber-500/30 bg-amber-500/10",
  orchestrator: "text-emerald-400 ring-emerald-500/30 bg-emerald-500/10",
  manager: "text-pink-400 ring-pink-500/30 bg-pink-500/10",
};

function confidenceBar(c: number): string {
  if (c >= 0.9) return "bg-emerald-500";
  if (c >= 0.7) return "bg-amber-500";
  return "bg-red-500";
}

export default function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
        No audit trail yet — the pipeline has not produced any decisions.
      </div>
    );
  }
  return (
    <ol className="relative space-y-4 border-l border-zinc-800 pl-6">
      {entries.map((e) => {
        const tone = agentTones[e.agent_name] ?? agentTones.orchestrator;
        return (
          <li key={e.id} className="relative">
            <span
              className={`absolute -left-[31px] top-1 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ring-1 ring-inset ${tone}`}
            >
              {e.agent_name.charAt(0).toUpperCase()}
            </span>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-200">
                    {agentLabel(e.agent_name)}
                  </span>
                  <span className="text-xs text-zinc-500">{e.action}</span>
                </div>
                <span className="text-xs tabular-nums text-zinc-500">
                  {fmtDateTime(e.created_at)}
                </span>
              </div>

              {e.reasoning && (
                <p className="mt-2 text-sm leading-relaxed text-zinc-300">
                  {e.reasoning}
                </p>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                {e.rule_fired && (
                  <span className="rounded-md bg-zinc-800 px-2 py-0.5 font-mono text-[11px] text-zinc-300">
                    rule: {e.rule_fired}
                  </span>
                )}
                <span className="inline-flex items-center gap-1.5 rounded-md bg-zinc-800/70 px-2 py-0.5 text-[11px] text-zinc-400">
                  confidence
                  <span className="font-semibold text-zinc-200">
                    {fmtConfidence(e.confidence)}
                  </span>
                  <span className="h-1 w-10 overflow-hidden rounded-full bg-zinc-700">
                    <span
                      className={`block h-full ${confidenceBar(e.confidence)}`}
                      style={{ width: `${Math.round(e.confidence * 100)}%` }}
                    />
                  </span>
                </span>
                {e.duration_ms > 0 && (
                  <span className="text-[11px] text-zinc-500">
                    {e.duration_ms}ms
                  </span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

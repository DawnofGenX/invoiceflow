"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AgentEvent } from "@/lib/api";
import { agentLabel, fmtConfidence } from "@/lib/format";

const agentTones: Record<string, string> = {
  intake: "text-sky-400",
  extraction: "text-violet-400",
  validation: "text-blue-400",
  approval: "text-amber-400",
  orchestrator: "text-emerald-400",
};

export default function AgentStream({
  invoiceId,
  onComplete,
}: {
  invoiceId: string;
  onComplete: (status: string) => void;
}) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [done, setDone] = useState(false);
  const doneRef = useRef(false);

  useEffect(() => {
    const es = new EventSource(api.streamUrl(invoiceId));

    es.addEventListener("agent_event", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data) as AgentEvent;
      setEvents((prev) => [...prev, data]);
      if (data.type === "invoice_completed" || data.type === "error") {
        if (!doneRef.current) {
          doneRef.current = true;
          setDone(true);
          es.close();
          onComplete(data.invoice_status ?? "error");
        }
      }
    });

    es.onerror = () => {
      if (!doneRef.current) {
        es.close();
        setDone(true);
        onComplete("stream_error");
      }
    };

    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Live agent run</h3>
        <span className="flex items-center gap-1.5 text-xs text-zinc-500">
          {done ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-zinc-500" />
              complete
            </>
          ) : (
            <>
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
              streaming
            </>
          )}
        </span>
      </div>
      <ol className="space-y-2 font-mono text-xs">
        {events.map((e, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-0.5 text-zinc-600">{">"}</span>
            <div>
              {e.type === "agent_started" && (
                <span className="text-zinc-400">
                  <span className={agentTones[e.agent ?? ""] ?? "text-zinc-200"}>
                    {agentLabel(e.agent ?? "")}
                  </span>{" "}
                  started{" "}
                  <span className="text-zinc-500">{e.action}</span>
                </span>
              )}
              {e.type === "agent_done" && (
                <span className="text-zinc-400">
                  <span className={agentTones[e.agent ?? ""] ?? "text-zinc-200"}>
                    {agentLabel(e.agent ?? "")}
                  </span>{" "}
                  done{" "}
                  {e.confidence != null && (
                    <span className="text-emerald-400">
                      ({fmtConfidence(e.confidence)})
                    </span>
                  )}
                  {e.rule_fired && (
                    <span className="text-amber-400"> [{e.rule_fired}]</span>
                  )}
                  {e.reasoning && (
                    <span className="block text-zinc-500">
                      ↳ {e.reasoning}
                    </span>
                  )}
                </span>
              )}
              {e.type === "invoice_completed" && (
                <span className="font-semibold text-emerald-400">
                  pipeline complete → {e.invoice_status}
                </span>
              )}
              {e.type === "error" && (
                <span className="font-semibold text-red-400">
                  error: {e.invoice_status}
                </span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

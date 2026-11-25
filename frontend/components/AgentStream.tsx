"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AgentEvent } from "@/lib/api";
import { agentLabel, fmtConfidence } from "@/lib/format";
import { StatusToken } from "@/components/StatusToken";

type Line = { ev: AgentEvent; at: string; n: number };

function clockNow() {
  return new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/**
 * The live run, printed into fixed cells. Each line prints in from the left
 * rather than sliding; the cursor stays visible while work is in flight.
 */
export default function AgentStream({
  invoiceId,
  onComplete,
}: {
  invoiceId: string;
  onComplete: (status: string) => void;
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [done, setDone] = useState(false);
  const doneRef = useRef(false);
  const countRef = useRef(0);

  useEffect(() => {
    const es = new EventSource(api.streamUrl(invoiceId));

    es.addEventListener("agent_event", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data) as AgentEvent;
      countRef.current += 1;
      setLines((prev) => [
        ...prev,
        { ev: data, at: clockNow(), n: countRef.current },
      ]);
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
    <section className="border border-rule-firm bg-slip">
      <header className="flex items-center justify-between border-b border-ink px-4 py-2.5">
        <div className="flex items-baseline gap-2">
          <span className="micro">Live run</span>
          <span className="num text-[10.5px] text-ink-mute">
            {String(lines.length).padStart(2, "0")} lines
          </span>
        </div>
        <span className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className={`h-[6px] w-[6px] ${
              done ? "border border-rule-firm" : "lamp-live bg-signal"
            }`}
          />
          <span className="micro !text-ink">
            {done ? "complete" : "streaming"}
          </span>
        </span>
      </header>

      <div
        role="log"
        aria-live="polite"
        aria-label="Agent decisions as they are made"
        className="max-h-[420px] overflow-auto"
      >
        {lines.length === 0 && (
          <p className="px-4 py-5 text-[12.5px] text-ink-mute">
            Waiting for the first agent to report…
          </p>
        )}
        <ol>
          {lines.map(({ ev, at, n }) => (
            <li
              key={n}
              className="printed grid grid-cols-[54px_78px_minmax(0,1fr)] gap-x-3 gap-y-1 border-b border-rule px-4 py-1.5 last:border-0"
            >
              <span className="num pt-[2px] text-[10px] text-ink-mute">
                {at}
              </span>
              <span className="pt-[1px] text-[10px] font-medium uppercase tracking-[0.08em] text-ink">
                {ev.agent ? agentLabel(ev.agent) : "System"}
              </span>

              <div className="min-w-0">
                {ev.type === "agent_started" && (
                  <span className="num text-[11px] text-ink-mute">
                    {ev.action} — started
                  </span>
                )}

                {ev.type === "agent_done" && (
                  <div>
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <span className="num text-[11px] text-ink-soft">
                        {ev.action}
                      </span>
                      {ev.confidence != null && (
                        <span className="num text-[10.5px] text-ink-mute">
                          {fmtConfidence(ev.confidence)}
                        </span>
                      )}
                      {ev.rule_fired && (
                        <span className="num rounded-[2px] border border-rule-firm px-1.5 py-[1px] text-[10px] text-ink">
                          {ev.rule_fired}
                        </span>
                      )}
                    </div>
                    {ev.reasoning && (
                      <p className="mt-1 max-w-[62ch] text-[12px] leading-[1.5] text-ink-soft">
                        {ev.reasoning}
                      </p>
                    )}
                  </div>
                )}

                {ev.type === "invoice_completed" && (
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="num text-[11px] text-ink">
                      pipeline closed
                    </span>
                    <StatusToken status={ev.invoice_status ?? "error"} />
                  </span>
                )}

                {ev.type === "error" && (
                  <span className="num text-[11px] text-void">
                    error · {ev.invoice_status}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>

        {!done && lines.length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2">
            <span
              aria-hidden="true"
              className="lamp-live inline-block h-[11px] w-[6px] bg-signal"
            />
            <span className="micro">printing</span>
          </div>
        )}
      </div>
    </section>
  );
}

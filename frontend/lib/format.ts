// Formatting helpers.

export function fmtMoney(n: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function fmtStamp(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
  });
  const time = d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${date} ${time}`;
}

export function fmtConfidence(c: number | null | undefined): string {
  if (c == null) return "—";
  return `${(c * 100).toFixed(1)}%`;
}

export function statusLabel(s: string): string {
  return s.replace(/_/g, " ");
}

/** Old tone vocabulary, kept for callers that only need a word. */
export function statusTone(s: string): string {
  return disposition(s).tone;
}

export type Tone = "settled" | "hold" | "void" | "live" | "neutral";

/**
 * The register vocabulary. A disposition is a stamped token, never a pill:
 * AUTO / HELD / VOID / SCHEDULED / PRINTING.
 */
export function disposition(s: string): { token: string; tone: Tone } {
  switch (s) {
    case "paid":
    case "approved":
      return { token: "SETTLED", tone: "settled" };
    case "payment_scheduled":
      return { token: "SCHEDULED", tone: "settled" };
    case "awaiting_approval":
      return { token: "HELD", tone: "hold" };
    case "needs_review":
      return { token: "REVIEW", tone: "hold" };
    case "rejected":
      return { token: "VOID", tone: "void" };
    case "error":
      return { token: "ERROR", tone: "void" };
    case "extracting":
    case "validating":
    case "pending":
      return { token: "PRINTING", tone: "live" };
    default:
      return { token: s.replace(/_/g, " ").toUpperCase(), tone: "neutral" };
  }
}

export function agentLabel(name: string): string {
  const labels: Record<string, string> = {
    intake: "Intake",
    extraction: "Extraction",
    validation: "Validation",
    approval: "Approval",
    orchestrator: "Orchestrator",
    manager: "Human",
  };
  return labels[name] ?? name;
}

/** Age of a record, in register shorthand: 12m / 6h / 3d. */
export function ageLabel(iso: string): string {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "—";
  const mins = Math.max(0, Math.floor((Date.now() - t) / 60000));
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** Register reference: stable short handle for an invoice uuid. */
export function shortRef(id: string): string {
  return id.replace(/-/g, "").slice(0, 8).toUpperCase();
}

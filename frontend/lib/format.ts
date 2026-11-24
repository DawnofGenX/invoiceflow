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

export function fmtConfidence(c: number | null | undefined): string {
  if (c == null) return "—";
  return `${Math.round(c * 100)}%`;
}

export function statusLabel(s: string): string {
  return s.replace(/_/g, " ");
}

export function statusTone(s: string): string {
  switch (s) {
    case "payment_scheduled":
    case "paid":
    case "approved":
      return "emerald";
    case "awaiting_approval":
      return "amber";
    case "needs_review":
      return "orange";
    case "rejected":
    case "error":
      return "red";
    case "extracting":
    case "validating":
      return "blue";
    default:
      return "zinc";
  }
}

export function agentLabel(name: string): string {
  const labels: Record<string, string> = {
    intake: "Intake Agent",
    extraction: "Extraction Agent",
    validation: "Validation Agent",
    approval: "Approval Agent",
    orchestrator: "Orchestrator",
    manager: "Human Manager",
  };
  return labels[name] ?? name;
}

// API client + types for the InvoiceFlow backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export type InvoiceStatus =
  | "pending"
  | "extracting"
  | "validating"
  | "needs_review"
  | "awaiting_approval"
  | "approved"
  | "payment_scheduled"
  | "paid"
  | "rejected"
  | "error";

export interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
  matched_po_line_id: string | null;
}

export interface AuditEntry {
  id: string;
  agent_name: string;
  action: string;
  reasoning: string;
  rule_fired: string | null;
  confidence: number;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  duration_ms: number;
  created_at: string;
}

export interface InvoiceSummary {
  id: string;
  invoice_number: string;
  vendor_name: string;
  vendor_email: string | null;
  amount: number;
  currency: string;
  tax_amount: number | null;
  invoice_date: string | null;
  due_date: string | null;
  po_number: string | null;
  status: InvoiceStatus;
  confidence_score: number | null;
  created_at: string;
}

export interface InvoiceDetail extends InvoiceSummary {
  raw_text: string | null;
  file_path: string | null;
  line_items: LineItem[];
  audit_entries: AuditEntry[];
}

export interface ApprovalRequest {
  id: string;
  invoice_id: string;
  approver_id: string | null;
  status: string;
  amount_threshold: number | null;
  reason: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface DashboardStats {
  total_invoices: number;
  by_status: Record<string, number>;
  total_amount: number;
  pending_approvals: number;
  needs_review: number;
  auto_approved: number;
}

export interface RecentDecision {
  id: string;
  invoice_id: string;
  invoice_number: string;
  vendor_name: string;
  agent: string;
  action: string;
  reasoning: string;
  rule_fired: string | null;
  confidence: number;
  duration_ms: number;
  created_at: string;
}

export interface AuditSummary {
  total_decisions: number;
  decisions_per_invoice: number;
  by_agent: Record<string, number>;
  rules_fired: Array<{ rule: string; count: number }>;
  avg_confidence: number | null;
  low_confidence_threshold: number;
  low_confidence_count: number;
  total_invoices: number;
  automated_invoices: number;
  human_review_invoices: number;
  automation_rate: number;
  by_status: Record<string, number>;
  recent: RecentDecision[];
}

export interface VendorRow {
  vendor_name: string;
  invoice_count: number;
  settled_count: number;
  total_amount: number;
  avg_confidence: number | null;
  last_seen: string | null;
  has_history: boolean;
}

export interface BatchUploadResult {
  filename: string;
  invoice_id: string | null;
  status: string;
  error: string | null;
}

export interface AgentEvent {
  type: string;
  agent?: string;
  action?: string;
  status?: string;
  reasoning?: string;
  confidence?: number;
  rule_fired?: string;
  invoice_status?: string;
  document_type?: string;
  vendor_name?: string;
  amount?: number;
  valid?: boolean;
  issues?: Array<{ check: string; severity: string; reason: string }>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<DashboardStats>("/api/dashboard/"),
  listInvoices: (params?: { status?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<InvoiceSummary[]>(`/api/invoices/${suffix}`);
  },
  auditSummary: () => request<AuditSummary>("/api/audit/summary"),
  vendors: () => request<VendorRow[]>("/api/vendors/"),
  getInvoice: (id: string) => request<InvoiceDetail>(`/api/invoices/${id}`),
  getAudit: (id: string) => request<AuditEntry[]>(`/api/invoices/${id}/audit`),
  listApprovals: () => request<ApprovalRequest[]>("/api/approvals/"),
  decide: (id: string, decision: "approve" | "reject", comment?: string) =>
    request<{ approval_status: string; invoice_status: string }>(
      `/api/approvals/${id}/decide`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, comment }),
      },
    ),
  upload: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ invoice_id: string; status: string }>(
      "/api/invoices/upload",
      { method: "POST", body: fd },
    );
  },
  uploadBatch: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return request<{ accepted: number; failed: number; results: BatchUploadResult[] }>(
      "/api/invoices/upload-batch",
      { method: "POST", body: fd },
    );
  },
  seed: () => request<{ seeded: boolean }>("/api/seed/", { method: "POST" }),
  streamUrl: (id: string) => `${API_URL}/api/invoices/${id}/stream`,
  exportUrl: (id: string, format: "json" | "pdf") =>
    `${API_URL}/api/invoices/${id}/audit/export?format=${format}`,
};

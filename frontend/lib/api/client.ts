import { toast } from "sonner";
import type { Alert, AlertPage, AuditEvent, Decision, Guideline, HealthStatus, InvestigationSummary, ReportResponse, SearchRequest, SearchResult, Transaction, UploadResult } from "@/lib/api/types";
import { auditEvents, createMockReport, investigations, mockAlerts, mockGuidelines, mockHealth, mockTransactions, reportResponses } from "@/lib/mocks/data";

const mockMode = () => process.env.NEXT_PUBLIC_USE_MOCKS !== "false";
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ragBase = (process.env.NEXT_PUBLIC_RAG_BASE_URL ?? "http://localhost:8001").replace(/\/$/, "");
const wait = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));
let nextInvestigation = 0;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json() as { detail?: string }; if (body.detail) detail = body.detail; } catch { /* use status message */ }
    toast.error(detail);
    const error = new Error(detail) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthStatus> {
    if (mockMode()) { await wait(120); return { ...mockHealth, checked_at: new Date().toISOString() }; }
    return request<HealthStatus>(`${apiBase}/health`);
  },
  async getAlerts(limit = 25, offset = 0): Promise<AlertPage> {
    const safeLimit = Math.min(200, Math.max(1, Math.trunc(limit)));
    const safeOffset = Math.max(0, Math.trunc(offset));
    if (mockMode()) { await wait(); return { items: mockAlerts.slice(safeOffset, safeOffset + safeLimit), total: mockAlerts.length, limit: safeLimit, offset: safeOffset }; }
    return request<AlertPage>(`${apiBase}/alerts?limit=${safeLimit}&offset=${safeOffset}`);
  },
  async getAlert(alertId: string): Promise<Alert> {
    if (mockMode()) { await wait(100); const alert = mockAlerts.find((item) => item.id === alertId); if (!alert) throw new Error("Alert not found."); return alert; }
    return request<Alert>(`${apiBase}/alerts/${encodeURIComponent(alertId)}`);
  },
  async uploadTransactions(file: File): Promise<UploadResult> {
    if (mockMode()) {
      await wait(650);
      const rows = Math.max(1, file.size ? Math.round(file.size / 145) : 20);
      const rejected = Math.max(1, Math.round(rows * 0.04));
      const rejectionReasons = [{ row_number: 4, reason: "Missing transaction timestamp." }, { row_number: 17, reason: "Unsupported currency code." }, { row_number: 26, reason: "Amount must be a decimal string." }];
      const visibleReasons = rejectionReasons.slice(0, rejected);
      return { dataset_id: `DATA-2026-${Date.now().toString().slice(-6)}`, accepted_count: rows - rejected, rejected_count: rejected, alerts_created: Math.round((rows - rejected) * 0.12), rejection_reasons: visibleReasons, rejection_reasons_truncated: rejected > visibleReasons.length };
    }
    const form = new FormData(); form.append("file", file);
    // The backend reports counts as accepted/rejected and rejections as {source_row, reasons[]}.
    const raw = await request<{ dataset_id: string; accepted: number; rejected: number; alerts_created: number; rejection_reasons: { source_row: number; reasons: string[] }[]; rejection_reasons_truncated: boolean }>(`${apiBase}/upload-transactions`, { method: "POST", body: form });
    return { dataset_id: raw.dataset_id, accepted_count: raw.accepted, rejected_count: raw.rejected, alerts_created: raw.alerts_created, rejection_reasons: raw.rejection_reasons.map((item) => ({ row_number: item.source_row, reason: item.reasons.join("; ") })), rejection_reasons_truncated: raw.rejection_reasons_truncated };
  },
  async getAccountHistory(token: string, limit = 100): Promise<Transaction[]> {
    if (mockMode()) { await wait(); return mockTransactions.slice(0, limit).map((row, index) => ({ ...row, sender_token: index % 2 ? token : row.sender_token, receiver_token: index % 2 ? row.receiver_token : token })); }
    return request<Transaction[]>(`${apiBase}/accounts/${encodeURIComponent(token)}/history?limit=${limit}`);
  },
  async investigateAlert(alertId: string): Promise<{ investigation_id: string; status: "PENDING_AGENT" }> {
    if (mockMode()) { await wait(450); const found = investigations.find((item) => item.alert_id === alertId); if (found && found.execution_status === "running") { const err = new Error("An investigation is already running for this alert.") as Error & { status: number }; err.status = 409; throw err; } const id = `INV-2026-${String(319 + nextInvestigation++).padStart(5, "0")}`; investigations.unshift({ investigation_id: id, alert_id: alertId, status: "PENDING_AGENT", execution_status: "running", verification: { passed: false, errors: [], warnings: [] }, created_at: new Date().toISOString() }); auditEvents[id] = [{ event_id: `EVT-${id.slice(-5)}-01`, action: "CREATED", details: { alert_id: alertId, actor: "analyst-ui" }, created_at: new Date().toISOString() }, { event_id: `EVT-${id.slice(-5)}-02`, action: "AGENT_RUN_REQUESTED", details: { actor: "analyst-ui" }, created_at: new Date().toISOString() }]; return { investigation_id: id, status: "PENDING_AGENT" }; }
    return request<{ investigation_id: string; status: "PENDING_AGENT" }>(`${apiBase}/investigate/${encodeURIComponent(alertId)}`, { method: "POST" });
  },
  async runInvestigation(investigationId: string): Promise<ReportResponse> {
    if (mockMode()) {
      await wait(1100);
      const summary = investigations.find((item) => item.investigation_id === investigationId);
      const alert = summary && mockAlerts.find((item) => item.id === summary.alert_id);
      if (!summary || !alert) throw new Error("Investigation or associated alert not found.");
      const template = reportResponses[0];
      const result: ReportResponse = { ...template, investigation_id: investigationId, report: createMockReport(investigationId, alert, "verified"), execution_status: "completed", verification: { passed: true, errors: [], warnings: ["Customer profile data was not included in the transaction sample."] }, agent_execution_trace: template.agent_execution_trace };
      summary.status = "COMPLETED";
      summary.execution_status = "completed";
      summary.verification = result.verification;
      reportResponses.unshift(result);
      auditEvents[investigationId]?.push({ event_id: `EVT-${investigationId.slice(-5)}-03`, action: "AGENT_RUN_FINISHED", details: { execution_status: "completed" }, created_at: new Date().toISOString() });
      return result;
    }
    // /run returns only a status summary; the report itself is read back from /report.
    const run = await request<{ execution_status: ReportResponse["execution_status"]; report_available: boolean }>(`${apiBase}/investigations/${encodeURIComponent(investigationId)}/run`, { method: "POST" });
    if (!run.report_available) throw new Error(`Investigation ${run.execution_status}; no report was produced.`);
    return request<ReportResponse>(`${apiBase}/investigations/${encodeURIComponent(investigationId)}/report`);
  },
  async getInvestigation(investigationId: string): Promise<InvestigationSummary> {
    if (mockMode()) { await wait(); const item = investigations.find((row) => row.investigation_id === investigationId); if (!item) throw new Error("Investigation not found."); return { ...item, verification: { ...item.verification, errors: [...item.verification.errors], warnings: [...item.verification.warnings] }, decision: item.decision ? { ...item.decision } : null }; }
    return request<InvestigationSummary>(`${apiBase}/investigations/${encodeURIComponent(investigationId)}`);
  },
  async getInvestigationReport(investigationId: string): Promise<ReportResponse> {
    if (mockMode()) {
      await wait(160);
      const report = reportResponses.find((row) => row.investigation_id === investigationId);
      if (report) return report;
      const summary = investigations.find((row) => row.investigation_id === investigationId);
      const alert = summary && mockAlerts.find((item) => item.id === summary.alert_id);
      if (!summary || !alert) throw new Error("Investigation report not found.");
      const variant = summary.execution_status === "failed" ? "failed" : summary.execution_status === "incomplete" ? "incomplete" : "verified";
      const template = reportResponses[0];
      return { ...template, investigation_id: investigationId, label: summary.execution_status === "running" ? "Agent run in progress" : template.label, report: createMockReport(investigationId, alert, variant), execution_status: summary.execution_status === "pending" ? "running" : summary.execution_status, verification: summary.verification };
    }
    return request<ReportResponse>(`${apiBase}/investigations/${encodeURIComponent(investigationId)}/report`);
  },
  async submitDecision(investigationId: string, decision: Decision): Promise<Decision> {
    if (mockMode()) { await wait(400); const summary = investigations.find((row) => row.investigation_id === investigationId); if (!summary) throw new Error("Investigation not found."); if (summary.decision) { const err = new Error("A human decision has already been recorded for this investigation.") as Error & { status: number }; err.status = 409; throw err; } if (decision.decision === "APPROVE" && (summary.execution_status !== "completed" || !summary.verification.passed)) throw new Error("Approval requires a completed, verified report."); summary.decision = { ...decision, created_at: new Date().toISOString() }; summary.status = decision.decision; auditEvents[investigationId]?.push({ event_id: `EVT-${investigationId.slice(-5)}-${String((auditEvents[investigationId]?.length ?? 0) + 1).padStart(2, "0")}`, action: "DECISION_RECORDED", details: { decision: decision.decision, analyst_id: decision.analyst_id, rationale: decision.rationale }, created_at: summary.decision.created_at }); return summary.decision; }
    return request<Decision>(`${apiBase}/investigations/${encodeURIComponent(investigationId)}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: decision.decision, rationale: decision.rationale, analyst_id: decision.analyst_id }) });
  },
  async getInvestigations(limit = 200): Promise<InvestigationSummary[]> {
    if (!mockMode()) return request<InvestigationSummary[]>(`${apiBase}/investigations?limit=${Math.min(200, Math.max(1, Math.trunc(limit)))}`);
    await wait();
    return investigations.map((item) => ({ ...item, verification: { ...item.verification, errors: [...item.verification.errors], warnings: [...item.verification.warnings] }, decision: item.decision ? { ...item.decision } : null }));
  },
  async searchGuidelines(input: SearchRequest): Promise<SearchResult> {
    if (mockMode()) { await wait(450); const matches = mockGuidelines.filter((item) => item.typology === input.typology || input.query.toLowerCase().split(/\s+/).some((word) => `${item.text} ${item.source}`.toLowerCase().includes(word))).slice(0, input.top_k); return { retrieved_guidelines: matches, source_references: matches.map((item) => item.source), relevance_notes: matches.length ? ["Results are ranked against the selected typology and query terms.", "Review retrieved passages in context before relying on them."] : [] }; }
    return request<SearchResult>(`${ragBase}/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) });
  },
  async getAudit(investigationId: string): Promise<AuditEvent[]> {
    if (mockMode()) { await wait(); return (auditEvents[investigationId] ?? []).map((event) => ({ ...event, details: { ...event.details } })); }
    return request<AuditEvent[]>(`${apiBase}/audit/${encodeURIComponent(investigationId)}`);
  },
};

export const appConfig = { apiBase, ragBase, mocks: mockMode() };

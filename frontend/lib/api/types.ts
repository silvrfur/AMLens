export type Typology = "structuring" | "rapid_movement" | "fan_in_out" | "unusual_activity";
export type GapStatus = "confirmed_missing" | "not_provided" | "not_applicable" | "available_verified";
export interface Alert { id: string; transaction_id: string; rule_id: string; description: string; evidence: Record<string, unknown>; status: string; created_at?: string | null; }
export interface Guideline { chunk_id: string; text: string; source: string; section: string; page: number | null; typology: string; relevance_score: number; }
export interface EvidenceFinding { claim_id: string; claim: string; claim_type: "observed_fact"|"supported_interpretation"|"unsupported_assumption"|"potential_concern"; supporting_transaction_ids: string[]; supporting_chunk_ids: string[]; evidence_explanation: string; support_status: "supported"|"limited"|"unsupported"; metric_key?: string | null; }
export interface InformationGap { field: string; status: GapStatus; explanation: string; question?: string | null; }
export interface Pattern { pattern_id: string; description: string; transaction_ids: string[]; metric_key: string; }
export interface TransactionAnalysis { observed_patterns: Pattern[]; potential_red_flags: string[]; supporting_transaction_ids: string[]; computed_statistics: Record<string, string | number>; limitations: string[]; }
export interface InvestigationReport {
  investigation_id: string;
  alert_summary: { alert_id: string; typology: string; account_id: string; summary: string };
  transaction_analysis: TransactionAnalysis;
  aml_guidance_and_evidence: { references: Guideline[]; evidence: EvidenceFinding[]; potential_concerns: string[]; unsupported_assumptions: string[] };
  missing_information_and_questions: { information_gaps: InformationGap[]; investigation_questions: string[] };
  investigation_narrative: { statements: string[]; recommended_next_steps: string[]; limitations: string[] };
  human_review_disclaimer: string;
}
export interface Verification { passed: boolean; errors: string[]; warnings: string[]; }
export interface ReportResponse { investigation_id: string; execution_status: "completed"|"incomplete"|"failed"|"running"; label: string; report: InvestigationReport; verification: Verification; agent_execution_trace: { agent_name: string; execution_status: string; error_message?: string | null }[]; }
export type InvestigationStatus = "PENDING_AGENT" | "RUNNING" | "COMPLETED" | "INCOMPLETE" | "FAILED" | "APPROVE" | "REJECT" | "ESCALATE";
export interface InvestigationSummary { investigation_id: string; alert_id: string; status: InvestigationStatus; execution_status: ReportResponse["execution_status"] | "pending"; verification: Verification; created_at: string; decision?: Decision | null; }
export interface Decision { decision: "APPROVE" | "REJECT" | "ESCALATE"; rationale: string; analyst_id: string; created_at: string; }
export interface Transaction { transaction_id: string; timestamp: string; sender_token: string; receiver_token: string; amount_paid: string; payment_currency: string; amount_received: string; receiving_currency: string; payment_format: string; }
export interface AuditEvent { event_id: string; action: "CREATED" | "AGENT_RUN_REQUESTED" | "AGENT_RUN_FINISHED" | "AGENT_RUN_FAILED" | "DECISION_RECORDED"; details: Record<string, unknown>; created_at: string; }
export interface UploadResult { dataset_id: string; accepted_count: number; rejected_count: number; alerts_created: number; rejection_reasons: { row_number: number; reason: string }[]; rejection_reasons_truncated: boolean; }
export interface HealthStatus { backend: "healthy" | "degraded" | "offline"; agent: "healthy" | "degraded" | "offline"; rag: "healthy" | "degraded" | "offline"; queue: "healthy" | "degraded" | "offline" | "not_applicable"; checked_at: string; }
export interface AlertPage { items: Alert[]; total: number; limit: number; offset: number; }
export interface SearchRequest { query: string; typology: Typology; top_k: number; }
export interface SearchResult { retrieved_guidelines: Guideline[]; source_references: string[]; relevance_notes: string[]; }

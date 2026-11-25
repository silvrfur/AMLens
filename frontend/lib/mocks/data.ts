import type { Alert, AuditEvent, Guideline, HealthStatus, InvestigationReport, InvestigationSummary, ReportResponse, Transaction } from "@/lib/api/types";

const rules = ["HIGH_VALUE", "REPEATED_PAIR", "RAPID_MOVEMENT_CANDIDATE"] as const;
const descriptions = [
  "Single payment exceeds the configured monitoring threshold.",
  "Repeated transfers between the same tokenized counterparties within a short period.",
  "Funds move across multiple counterparties shortly after receipt.",
  "Multiple incoming transfers aggregate before an outbound payment.",
  "Activity differs from the account's recent observed transaction pattern.",
];
const amounts = ["12450.00", "8750.00", "25000.00", "4999.50", "18200.00", "7600.00", "31000.00", "9950.25", "6400.00", "14250.00", "5200.00", "22800.00", "11800.00", "9700.00", "15750.00", "6800.00", "34500.00", "8900.00", "12750.00", "5400.00", "20500.00", "7350.00", "16400.00", "11200.00", "29800.00"];
const accounts = ["ACC-****4F2A", "ACC-****91C8", "ACC-****0D7B", "ACC-****A53E", "ACC-****C219", "ACC-****7B04", "ACC-****E810", "ACC-****3A66"];
export const mockAlerts: Alert[] = amounts.map((amount, index) => {
  const rule = rules[index % rules.length];
  const date = new Date(Date.UTC(2026, 10, 22 - Math.floor(index / 3), 16 - (index % 12), 12 + (index % 45)));
  const status = index === 0 ? "UNDER REVIEW" : index === 3 ? "DECIDED" : "OPEN";
  const txnId = `TXN-2026-${String(7184 + index).padStart(5, "0")}`;
  return {
    id: `ALT-2026-${String(4821 + index).padStart(5, "0")}`,
    transaction_id: txnId,
    rule_id: rule,
    description: descriptions[index % descriptions.length],
    status,
    evidence: {
      transaction_ids: [txnId, `TXN-2026-${String(7102 + index).padStart(5, "0")}`],
      anchor_account_token: accounts[index % accounts.length],
      amount_paid: amount,
      currency: "USD",
      threshold: "10000.00",
      created_at: date.toISOString(),
      sender_token: accounts[index % accounts.length],
      receiver_token: accounts[(index + 3) % accounts.length],
      payment_format: index % 2 ? "SWIFT" : "ACH",
      observed_window: "24 hours",
    },
  };
});

export const mockGuidelines: Guideline[] = [
  { chunk_id: "FATF-R10-03-014", text: "Financial institutions should conduct ongoing due diligence on the business relationship and scrutinise transactions undertaken throughout the course of that relationship to ensure that the transactions being conducted are consistent with the institution's knowledge of the customer, their business and risk profile, including, where necessary, the source of funds.", source: "FATF Recommendations", section: "Recommendation 10 — Customer due diligence", page: 14, typology: "unusual_activity", relevance_score: 0.94 },
  { chunk_id: "RBI-KYC-23-07-02", text: "Banks should examine the background and purpose of transactions which are complex, unusually large, and have no apparent economic or lawful purpose. Background and purpose of such transactions should, as far as possible, be examined, and written findings should be available with the bank.", source: "RBI KYC Master Direction", section: "Section 7 — Monitoring of Transactions", page: 28, typology: "unusual_activity", relevance_score: 0.91 },
  { chunk_id: "FIU-IND-STR-04-011", text: "Institutions should give particular attention to transactions that have no apparent economic or visible lawful purpose, including unusual patterns of transactions that are inconsistent with the customer's known profile.", source: "FIU-IND Guidance", section: "Chapter 4 — Suspicious transaction indicators", page: 11, typology: "rapid_movement", relevance_score: 0.88 },
  { chunk_id: "FATF-R10-04-022", text: "Where the financial institution is unable to comply with relevant customer due diligence requirements, it should consider making a suspicious transaction report in relation to the customer.", source: "FATF Recommendations", section: "Recommendation 10 — Customer due diligence", page: 16, typology: "structuring", relevance_score: 0.86 },
  { chunk_id: "RBI-KYC-23-09-01", text: "Banks shall have appropriate systems and procedures to identify and report suspicious transactions, whether or not made in cash, to the Director, Financial Intelligence Unit-India.", source: "RBI KYC Master Direction", section: "Section 9 — Reporting Requirements", page: 33, typology: "fan_in_out", relevance_score: 0.83 },
  { chunk_id: "FIU-IND-STR-03-008", text: "The reporting entity should maintain a record of the rationale for determining that a transaction or a series of transactions is unusual and the grounds on which the decision to report or not to report was made.", source: "FIU-IND Guidance", section: "Chapter 3 — Internal review", page: null, typology: "structuring", relevance_score: 0.79 },
];

const disclaimer = "This AI-generated report is a decision-support draft only. It is not a finding of wrongdoing and does not replace investigator judgment. The investigator is responsible for verifying evidence and recording any final decision.";
export function createMockReport(id: string, alert: Alert, variant: "verified" | "incomplete" | "failed"): InvestigationReport {
  const account = String(alert.evidence.anchor_account_token);
  const txnIds = alert.evidence.transaction_ids as string[];
  return {
    investigation_id: id,
    alert_summary: { alert_id: alert.id, typology: variant === "verified" ? "rapid_movement" : "unusual_activity", account_id: account, summary: `Automated review of ${txnIds.length} linked payment records identified activity that meets the ${alert.rule_id} monitoring rule. This summary is descriptive and requires investigator validation.` },
    transaction_analysis: {
      observed_patterns: [{ pattern_id: "PAT-01", description: "An outbound payment was recorded within the observed window after multiple inbound transfers.", transaction_ids: txnIds, metric_key: "outbound_after_inbound_window" }],
      potential_red_flags: ["Transaction value is above the configured review threshold.", "Counterparty activity may warrant contextual review."],
      supporting_transaction_ids: txnIds,
      computed_statistics: { "observed_transaction_count": variant === "failed" ? "0" : "7", "total_inbound_usd": variant === "incomplete" ? "48150.00" : "62450.00", "largest_single_payment_usd": String(alert.evidence.amount_paid), "median_gap_minutes": "18.5" },
      limitations: variant === "failed" ? ["Transaction history could not be retrieved; no statistical conclusions are available."] : ["Source-of-funds and customer profile information were not available to the agent.", "Values reflect the retrieved sample only and may not represent complete account activity."],
    },
    aml_guidance_and_evidence: {
      references: mockGuidelines.slice(0, variant === "failed" ? 1 : 3),
      evidence: [
        { claim_id: "CLM-01", claim: `A payment of ${String(alert.evidence.amount_paid)} ${String(alert.evidence.currency)} was present in the alert evidence.`, claim_type: "observed_fact", supporting_transaction_ids: [alert.transaction_id], supporting_chunk_ids: [], evidence_explanation: "Copied from the alert payload; this is an observed input and was not independently reconciled to a statement.", support_status: "supported", metric_key: "largest_single_payment_usd" },
        { claim_id: "CLM-02", claim: "The observed timing may warrant review against the customer's expected activity.", claim_type: "supported_interpretation", supporting_transaction_ids: txnIds, supporting_chunk_ids: ["FATF-R10-03-014", "RBI-KYC-23-07-02"], evidence_explanation: "Guidance supports ongoing monitoring and review of transactions against the known customer profile. The customer profile was not included in this dataset.", support_status: variant === "failed" ? "unsupported" : "limited" },
        { claim_id: "CLM-03", claim: "The activity could relate to a change in business operations.", claim_type: "potential_concern", supporting_transaction_ids: [], supporting_chunk_ids: ["FIU-IND-STR-04-011"], evidence_explanation: "Possible context only. No corroborating business information is available in the supplied records.", support_status: "limited" },
      ],
      potential_concerns: ["The customer activity profile is not present in the supplied records.", "Payment purpose is not available for the outbound transaction."],
      unsupported_assumptions: ["No inference about intent or wrongdoing can be made from the supplied records alone."],
    },
    missing_information_and_questions: {
      information_gaps: [
        { field: "kyc", status: variant === "verified" ? "available_verified" : "not_provided", explanation: "Customer due diligence records were not included in the alert package.", question: "Does the current customer profile explain the observed activity?" },
        { field: "source_of_funds", status: "confirmed_missing", explanation: "No source-of-funds documentation was available for review.", question: "Can the source of funds be established from existing records?" },
        { field: "transaction_purpose", status: "not_provided", explanation: "Payment purpose was not included in the transaction feed.", question: "What is the stated purpose of the payment?" },
        { field: "sender_beneficiary_relationship", status: "not_applicable", explanation: "Relationship data was not required in this sample review." },
        { field: "counterparty_information", status: "confirmed_missing", explanation: "Counterparty profile details are not present in the uploaded dataset." },
      ],
      investigation_questions: ["Is the activity consistent with the stated customer profile and expected account use?", "Are supporting documents available to explain the payment purpose?"],
    },
    investigation_narrative: {
      statements: ["The alert was generated by a configured transaction monitoring rule.", "The agent identified a potential timing pattern from the available transaction sample.", "Available information is insufficient to determine whether the activity is consistent with the customer's profile."],
      recommended_next_steps: ["Review the current KYC profile and expected activity.", "Obtain and assess the payment purpose and available supporting documentation.", "Document the investigator's rationale and disposition in the case record."],
      limitations: ["This is an AI-generated draft based only on the data returned to the application.", "No external customer records or real-time monitoring were used."],
    },
    human_review_disclaimer: disclaimer,
  };
}

export const reportResponses: ReportResponse[] = [
  { investigation_id: "INV-2026-00318", execution_status: "completed", label: "Agent run complete", report: createMockReport("INV-2026-00318", mockAlerts[0], "verified"), verification: { passed: true, errors: [], warnings: ["Customer profile data was not included in the uploaded transaction sample."] }, agent_execution_trace: [{ agent_name: "Transaction Analysis", execution_status: "completed" }, { agent_name: "AML Knowledge Retrieval", execution_status: "completed" }, { agent_name: "Evidence Correlation", execution_status: "completed" }, { agent_name: "Information Gap", execution_status: "completed" }, { agent_name: "Report Drafting", execution_status: "completed" }, { agent_name: "Verifier", execution_status: "completed" }] },
  { investigation_id: "INV-2026-00317", execution_status: "incomplete", label: "Draft needs additional review", report: createMockReport("INV-2026-00317", mockAlerts[1], "incomplete"), verification: { passed: false, errors: [], warnings: ["Two transaction references could not be reconciled to the source sample.", "Source-of-funds documentation is unavailable."] }, agent_execution_trace: [{ agent_name: "Transaction Analysis", execution_status: "completed" }, { agent_name: "AML Knowledge Retrieval", execution_status: "completed" }, { agent_name: "Evidence Correlation", execution_status: "completed" }, { agent_name: "Information Gap", execution_status: "completed" }, { agent_name: "Report Drafting", execution_status: "completed" }, { agent_name: "Verifier", execution_status: "warning", error_message: "Report has unresolved supporting-data gaps." }] },
  { investigation_id: "INV-2026-00316", execution_status: "failed", label: "Agent run failed", report: createMockReport("INV-2026-00316", mockAlerts[2], "failed"), verification: { passed: false, errors: ["Transaction-history service returned no records.", "Evidence references could not be validated against the source dataset."], warnings: ["The narrative is incomplete and should not be used as a basis for a decision."] }, agent_execution_trace: [{ agent_name: "Transaction Analysis", execution_status: "failed", error_message: "Upstream transaction history was unavailable." }, { agent_name: "AML Knowledge Retrieval", execution_status: "completed" }, { agent_name: "Evidence Correlation", execution_status: "skipped" }, { agent_name: "Information Gap", execution_status: "skipped" }, { agent_name: "Report Drafting", execution_status: "skipped" }, { agent_name: "Verifier", execution_status: "failed", error_message: "Required evidence validation could not complete." }] },
];

export const investigations: InvestigationSummary[] = reportResponses.map((item, index) => ({ investigation_id: item.investigation_id, alert_id: item.report.alert_summary.alert_id, status: item.execution_status === "completed" ? "COMPLETED" : item.execution_status === "incomplete" ? "INCOMPLETE" : "FAILED", execution_status: item.execution_status, verification: item.verification, created_at: new Date(Date.UTC(2026, 10, 23 - index, 15, 20)).toISOString(), decision: null }));

export const mockTransactions: Transaction[] = Array.from({ length: 12 }, (_, index) => ({
  transaction_id: `TXN-2026-${String(7102 + index).padStart(5, "0")}`,
  timestamp: new Date(Date.UTC(2026, 10, 22 - Math.floor(index / 4), 8 + ((index * 3) % 12), 15 + (index % 40))).toISOString(),
  sender_token: accounts[index % accounts.length], receiver_token: accounts[(index + 2) % accounts.length],
  amount_paid: amounts[(index + 5) % amounts.length], payment_currency: "USD", amount_received: amounts[(index + 5) % amounts.length], receiving_currency: "USD", payment_format: index % 2 ? "SWIFT" : "ACH",
}));

function auditFor(investigationId: string, alertId: string, status: string): AuditEvent[] {
  const base = investigationId.endsWith("318") ? "2026-11-23T15:20:00Z" : investigationId.endsWith("317") ? "2026-11-22T14:45:00Z" : "2026-11-21T13:10:00Z";
  const start = Date.parse(base);
  const actions: AuditEvent["action"][] = ["CREATED", "AGENT_RUN_REQUESTED", status === "failed" ? "AGENT_RUN_FAILED" : "AGENT_RUN_FINISHED"];
  return actions.map((action, index) => ({ event_id: `EVT-${investigationId.slice(-5)}-${String(index + 1).padStart(2, "0")}`, action, details: { investigation_id: investigationId, alert_id: alertId, execution_status: status, actor: index === 0 ? "analyst-ui" : "agent-service" }, created_at: new Date(start + index * 120000).toISOString() }));
}
export const auditEvents: Record<string, AuditEvent[]> = Object.fromEntries(investigations.map((item) => [item.investigation_id, auditFor(item.investigation_id, item.alert_id, item.execution_status)]));
export const mockHealth: HealthStatus = { backend: "healthy", agent: "healthy", rag: "healthy", queue: "healthy", checked_at: new Date().toISOString() };

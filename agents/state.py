from typing import TypedDict, Any
from .schemas.agent_outputs import TransactionAnalysis, Guideline, EvidenceFinding, InformationGap
from .schemas.investigation import AlertContext, Transaction
from .schemas.report import InvestigationReport, VerificationResult

class InvestigationState(TypedDict, total=False):
    investigation_id: str
    alert_id: str
    execution_status: str
    alert_context: AlertContext
    account_id: str
    transactions: list[Transaction]
    transaction_analysis: TransactionAnalysis
    retrieved_guidelines: list[Guideline]
    source_references: list[str]
    relevance_notes: list[str]
    evidence_findings: list[EvidenceFinding]
    missing_information: list[InformationGap]
    investigation_questions: list[str]
    final_report: InvestigationReport | None
    verification_result: VerificationResult
    agent_execution_trace: list[dict[str, Any]]
    errors: list[str]
    retry_count: int
    lease_owner: str

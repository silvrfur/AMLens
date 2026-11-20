from typing import Literal
from pydantic import Field
from .investigation import StrictModel
from .agent_outputs import TransactionAnalysis, Guideline, EvidenceFinding, InformationGap

HUMAN_DISCLAIMER = "Human review required. Only a human investigator may escalate, request additional information, or close an alert as a false positive. This report is not a determination of criminal activity."

class AlertSummary(StrictModel):
    alert_id: str
    typology: str
    account_id: str
    summary: str

class GuidanceSection(StrictModel):
    references: list[Guideline]
    evidence: list[EvidenceFinding]
    potential_concerns: list[str]
    unsupported_assumptions: list[str]

class GapSection(StrictModel):
    information_gaps: list[InformationGap]
    investigation_questions: list[str]

class NarrativeSection(StrictModel):
    # A constrained narrative: every sentence must match an approved evidence-grounded sentence.
    statements: list[str] = Field(min_length=1)
    recommended_next_steps: list[Literal[
        "Review the cited transactions and guidance.",
        "Confirm the availability of the listed case information.",
        "Assess the documented concerns with a human investigator."
    ]] = Field(min_length=1)
    limitations: list[str]

class InvestigationReport(StrictModel):
    investigation_id: str
    alert_summary: AlertSummary
    transaction_analysis: TransactionAnalysis
    aml_guidance_and_evidence: GuidanceSection
    missing_information_and_questions: GapSection
    investigation_narrative: NarrativeSection
    human_review_disclaimer: str

class VerificationResult(StrictModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

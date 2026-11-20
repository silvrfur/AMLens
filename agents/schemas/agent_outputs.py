from typing import Literal
from pydantic import Field
from .investigation import StrictModel, GapStatus

class Pattern(StrictModel):
    pattern_id: str
    description: str
    transaction_ids: list[str]
    metric_key: str

class TransactionAnalysis(StrictModel):
    observed_patterns: list[Pattern]
    potential_red_flags: list[str]
    supporting_transaction_ids: list[str]
    # Money stored as exact decimal strings, totals segregated by currency.
    computed_statistics: dict[str, str | int]
    limitations: list[str]

class Guideline(StrictModel):
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    section: str
    page: int | None = Field(default=None, ge=1)
    typology: str
    relevance_score: float = Field(ge=-1, le=1)

class RetrievalResult(StrictModel):
    retrieved_guidelines: list[Guideline] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    relevance_notes: list[str] = Field(default_factory=list)

class EvidenceFinding(StrictModel):
    claim_id: str
    claim: str
    claim_type: Literal["observed_fact", "supported_interpretation", "unsupported_assumption", "potential_concern"]
    supporting_transaction_ids: list[str]
    supporting_chunk_ids: list[str]
    evidence_explanation: str
    support_status: Literal["supported", "limited", "unsupported"]
    metric_key: str | None = None

class InformationGap(StrictModel):
    field: str
    status: GapStatus
    explanation: str
    question: str | None = None

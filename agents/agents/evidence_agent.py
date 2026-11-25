from ..schemas.agent_outputs import EvidenceFinding

# Minimum relevance for citing a retrieved passage. Calibrated 2026-11-24 against the
# live Azure index (text-embedding-3-small): human-verified passages for the agents'
# typology queries score 0.46-0.66, passages on other AML topics at most 0.37.
# Re-check if the embedding model or the guidance corpus changes.
CITATION_MIN_RELEVANCE = 0.45

class EvidenceAgent:
    def __call__(self, state):
        findings = []
        for index, pattern in enumerate(state['transaction_analysis'].observed_patterns, 1):
            findings.append(EvidenceFinding(claim_id=f'FACT-{index}', claim=pattern.description,
                claim_type='observed_fact', supporting_transaction_ids=pattern.transaction_ids,
                supporting_chunk_ids=[], evidence_explanation='Reproducible deterministic pattern; see linked metric.',
                support_status='supported', metric_key=pattern.metric_key))
        chunks = [g for g in state['retrieved_guidelines'] if g.relevance_score >= CITATION_MIN_RELEVANCE and g.typology == state['alert_context'].typology]
        if chunks and findings:
            findings.append(EvidenceFinding(claim_id='INTERPRETATION-1',
                claim='Retrieved guidance provides context for reviewing the observed activity.',
                claim_type='supported_interpretation', supporting_transaction_ids=state['transaction_analysis'].supporting_transaction_ids,
                supporting_chunk_ids=[g.chunk_id for g in chunks],
                evidence_explanation='Typology and relevance align; this establishes contextual relevance only, not legal applicability or wrongdoing.', support_status='limited'))
            findings.append(EvidenceFinding(claim_id='CONCERN-1', claim='The observed patterns may warrant review of economic rationale.',
                claim_type='potential_concern', supporting_transaction_ids=state['transaction_analysis'].supporting_transaction_ids,
                supporting_chunk_ids=[g.chunk_id for g in chunks], evidence_explanation='A review question, not proof of misconduct.', support_status='limited'))
        findings.append(EvidenceFinding(claim_id='ASSUMPTION-1', claim='Intent and economic purpose cannot be established from transaction patterns alone.',
            claim_type='unsupported_assumption', supporting_transaction_ids=[], supporting_chunk_ids=[],
            evidence_explanation='No claim about customer intent is supported by this dataset.', support_status='unsupported'))
        return {'evidence_findings': findings}

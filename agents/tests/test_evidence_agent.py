from agents.agents.evidence_agent import EvidenceAgent

def test_traceable_claims(state):
    findings=state['evidence_findings']
    assert {f.claim_type for f in findings} == {'observed_fact','supported_interpretation','unsupported_assumption','potential_concern'}
    for f in findings:
        if f.claim_type=='observed_fact':
            assert f.metric_key in state['transaction_analysis'].computed_statistics
            assert f.supporting_transaction_ids
        if f.claim_type=='supported_interpretation': assert f.supporting_chunk_ids
        if f.claim_type=='unsupported_assumption': assert f.support_status=='unsupported'

def test_no_guidance_no_interpretation(state):
    state['retrieved_guidelines']=[]
    findings=EvidenceAgent()(state)['evidence_findings']
    assert not any(f.claim_type=='supported_interpretation' for f in findings)

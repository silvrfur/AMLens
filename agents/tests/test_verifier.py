import pytest
from agents.agents.report_agent import canonical_report
from agents.verifier.report_verifier import ReportVerifier

def test_accepts_grounded_report(state):
    state['final_report']=canonical_report(state)
    result=ReportVerifier().verify(state)
    assert result.passed and result.warnings

@pytest.mark.parametrize('attack', ['number','transaction','citation','source','assumption','disclaimer','section','prose_number','prose_words','accusation','gap','limitation'])
def test_rejects_tampering(state, attack):
    report=canonical_report(state)
    if attack=='number': report.transaction_analysis.computed_statistics['USD.total']='999999.00'
    elif attack=='transaction': report.aml_guidance_and_evidence.evidence[0].supporting_transaction_ids=['FAKE']
    elif attack=='citation': report.aml_guidance_and_evidence.evidence[0].supporting_chunk_ids=['FAKE']
    elif attack=='source': report.aml_guidance_and_evidence.references[0].source='Invented Authority'
    elif attack=='assumption': report.aml_guidance_and_evidence.evidence[-1].support_status='supported'
    elif attack=='disclaimer': report.human_review_disclaimer=''
    elif attack=='section':
        report=report.model_dump(); del report['alert_summary']
    elif attack=='prose_number': report.investigation_narrative.statements=['The total is 999999.00.']
    elif attack=='prose_words': report.investigation_narrative.statements=['The total is a million dollars.']
    elif attack=='accusation': report.investigation_narrative.statements=['This customer is guilty.']
    elif attack=='gap': report.missing_information_and_questions.information_gaps[0].status='confirmed_missing'
    elif attack=='limitation': report.investigation_narrative.limitations=[]
    state['final_report']=report
    assert not ReportVerifier().verify(state).passed

@pytest.mark.parametrize('action', ['Close the alert as a false positive.', 'Escalate automatically.', 'Request additional information automatically.'])
def test_no_decision_action(state, action):
    report=canonical_report(state)
    report.investigation_narrative.recommended_next_steps=[action]
    state['final_report']=report
    assert not ReportVerifier().verify(state).passed

def test_report_cannot_mutate_grounding(state):
    report=canonical_report(state)
    report.aml_guidance_and_evidence.references[0].source='Changed'
    assert state['retrieved_guidelines'][0].source!='Changed'

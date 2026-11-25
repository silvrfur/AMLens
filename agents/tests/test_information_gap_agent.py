from agents.agents.information_gap_agent import InformationGapAgent

def test_absence_is_not_confirmed_missing(state):
    assert all(g.status=='not_provided' for g in state['missing_information'])
    assert len(state['investigation_questions'])==7

def test_explicit_statuses(state):
    state['alert_context'].information_status={'kyc':'available_verified','source_of_funds':'confirmed_missing','supporting_documents':'not_applicable'}
    result=InformationGapAgent()(state)
    gaps={g.field:g for g in result['missing_information']}
    assert gaps['kyc'].question is None
    assert gaps['source_of_funds'].question
    assert gaps['supporting_documents'].status=='not_applicable'

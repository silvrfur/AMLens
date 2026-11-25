from agents.agents.report_agent import ReportAgent
from agents.schemas.report import HUMAN_DISCLAIMER

def test_report_complete_and_shared_llm(state, services):
    report=ReportAgent(services.llm)(state)['final_report']
    assert report.human_review_disclaimer==HUMAN_DISCLAIMER
    assert report.alert_summary.account_id.startswith('acct_')
    assert report.aml_guidance_and_evidence.references==state['retrieved_guidelines']
    assert len(services.llm.calls)==1

def test_prompt_has_no_account_or_description(state, services):
    ReportAgent(services.llm)(state)
    prompt=str(services.llm.calls)
    assert 'synthetic-account-A' not in prompt
    assert 'Synthetic customer receipt' not in prompt

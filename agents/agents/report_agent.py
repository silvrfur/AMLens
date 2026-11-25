from pydantic import Field
from ..schemas.investigation import StrictModel
from ..schemas.report import InvestigationReport, HUMAN_DISCLAIMER
from ..services.security import safe_llm_payload
from ..prompts.agent_prompts import REPORT_SYSTEM

class NarrativeDraft(StrictModel):
    statements: list[str] = Field(min_length=1)
    recommended_next_steps: list[str] = Field(min_length=1)

NEXT_STEPS = ['Review the cited transactions and guidance.',
              'Confirm the availability of the listed case information.',
              'Assess the documented concerns with a human investigator.']

def approved_statements(state):
    return ['The observed activity requires contextual human review.'] + [f.claim for f in state['evidence_findings']]

def canonical_report(state):
    return InvestigationReport.model_validate({
        'investigation_id': state['investigation_id'],
        'alert_summary': {'alert_id': state['alert_id'], 'typology': state['alert_context'].typology,
            'account_id': state['account_id'], 'summary': 'Transaction alert prepared for human investigation.'},
        'transaction_analysis': state['transaction_analysis'],
        'aml_guidance_and_evidence': {'references': state['retrieved_guidelines'], 'evidence': state['evidence_findings'],
            'potential_concerns': [f.claim for f in state['evidence_findings'] if f.claim_type == 'potential_concern'],
            'unsupported_assumptions': [f.claim for f in state['evidence_findings'] if f.support_status == 'unsupported']},
        'missing_information_and_questions': {'information_gaps': state['missing_information'], 'investigation_questions': state['investigation_questions']},
        'investigation_narrative': {'statements': approved_statements(state), 'recommended_next_steps': NEXT_STEPS,
            'limitations': state['transaction_analysis'].limitations + state.get('relevance_notes', [])},
        'human_review_disclaimer': HUMAN_DISCLAIMER}).model_copy(deep=True)

class ReportAgent:
    def __init__(self, llm): self.llm = llm
    def __call__(self, state):
        report = canonical_report(state)
        payload = safe_llm_payload(report.model_dump(mode='json'), approved_statements(state))
        payload['correction_requested'] = state.get('retry_count', 0) > 0
        # Validation errors are handled by the graph's single correction route.
        draft = self.llm.generate_structured_response(REPORT_SYSTEM, payload, NarrativeDraft)
        body = report.model_dump(mode='json')
        body['investigation_narrative'].update(draft.model_dump())
        return {'final_report': InvestigationReport.model_validate(body)}

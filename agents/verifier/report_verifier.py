import re
from ..schemas.report import InvestigationReport, VerificationResult, HUMAN_DISCLAIMER
from ..agents.transaction_agent import analyse
from ..agents.evidence_agent import EvidenceAgent
from ..agents.information_gap_agent import InformationGapAgent
from ..agents.report_agent import canonical_report, approved_statements

ACCUSATORY = re.compile(r'\b(guilty|criminal|launderer|money laundering confirmed|proves? laundering)\b', re.I)

class ReportVerifier:
    def verify(self, state):
        errors, warnings = [], []
        if state.get('final_report') is None:
            return VerificationResult(passed=False, errors=['Missing or invalid structured report'])
        try:
            report = InvestigationReport.model_validate(state['final_report'])
            # Independently recompute financial and evidence fields instead of trusting the draft.
            trusted = dict(state)
            trusted['transaction_analysis'] = analyse(state['transactions'])
            trusted.update(EvidenceAgent()(trusted))
            trusted.update(InformationGapAgent()(trusted))
            expected = canonical_report(trusted)
            for field in ('investigation_id','alert_summary','transaction_analysis','aml_guidance_and_evidence','missing_information_and_questions','human_review_disclaimer'):
                if getattr(report, field) != getattr(expected, field):
                    errors.append(f'{field}: differs from verified evidence or required content')
            if report.investigation_narrative.limitations != expected.investigation_narrative.limitations:
                errors.append('Limitations were changed or omitted')
            allowed = set(approved_statements(trusted))
            for sentence in report.investigation_narrative.statements:
                if sentence not in allowed:
                    errors.append('Narrative contains an unverified factual, numerical or citation claim')
                if ACCUSATORY.search(sentence): errors.append('Accusatory language in narrative')
            transactions = {t.transaction_id for t in state['transactions']}
            chunks = {g.chunk_id for g in state['retrieved_guidelines']}
            for claim in report.aml_guidance_and_evidence.evidence:
                if not set(claim.supporting_transaction_ids) <= transactions: errors.append('Unknown transaction reference')
                if not set(claim.supporting_chunk_ids) <= chunks: errors.append('Fabricated guidance reference')
                if claim.claim_type == 'observed_fact' and not claim.supporting_transaction_ids: errors.append('Observed fact lacks transaction evidence')
                if claim.claim_type == 'supported_interpretation' and not claim.supporting_chunk_ids: errors.append('Interpretation lacks guidance evidence')
                if claim.claim_type == 'unsupported_assumption':
                    if claim.support_status != 'unsupported': errors.append('Unsupported assumption not flagged')
                    warnings.append(claim.claim)
            if not chunks: warnings.append('No retrieved guidance available')
        except (ValueError, TypeError, KeyError):
            errors.append('Report or evidence failed schema validation')
        return VerificationResult(passed=not errors, errors=errors, warnings=warnings)

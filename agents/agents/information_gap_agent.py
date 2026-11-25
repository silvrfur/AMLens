from ..schemas.agent_outputs import InformationGap
FIELDS = {
    'kyc': 'What verified KYC information is available?',
    'source_of_funds': 'What evidence explains the source of funds?',
    'transaction_purpose': 'What is the purpose of the highlighted transactions?',
    'sender_beneficiary_relationship': 'What relationship links the sender and beneficiary?',
    'counterparty_information': 'What verified counterparty information is available?',
    'economic_rationale': 'What economic rationale explains the activity?',
    'supporting_documents': 'Which supporting documents are available for review?',
}
EXPLANATIONS = {
    'not_provided': 'Not provided to this workflow; availability in the case is unknown.',
    'confirmed_missing': 'The backend explicitly reports this information as missing.',
    'not_applicable': 'The backend explicitly marks this information not applicable.',
    'available_verified': 'The backend attests that this information is available and verified.',
}
class InformationGapAgent:
    def __call__(self, state):
        statuses = state['alert_context'].information_status
        gaps = [InformationGap(field=field, status=statuses.get(field, 'not_provided'),
            explanation=EXPLANATIONS[statuses.get(field, 'not_provided')],
            question=question if statuses.get(field, 'not_provided') in ('confirmed_missing','not_provided') else None)
            for field, question in FIELDS.items()]
        return {'missing_information': gaps, 'investigation_questions': [g.question for g in gaps if g.question]}

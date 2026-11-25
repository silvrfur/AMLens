from ..services.audit_service import consume

class MockGroqClient:
    """Fault injection is driven by the correction flag, safe across concurrent investigations."""
    def __init__(self, fail_first=False, always_fail=False):
        self.fail_first, self.always_fail = fail_first, always_fail
        self.calls = []
    def generate_structured_response(self, system_prompt, user_input, response_schema):
        consume('llm.generate')
        self.calls.append(user_input)
        statements = user_input['allowed_statements'][:]
        if self.always_fail or (self.fail_first and not user_input.get('correction_requested')):
            statements = ['The customer transferred 999999 USD.']
        return response_schema.model_validate({'statements': statements,
            'recommended_next_steps': user_input['allowed_next_steps']})

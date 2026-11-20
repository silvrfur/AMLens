import pytest
from agents.graph import InvestigationRunner, InvestigationFailed
from agents.mocks.mock_backend import MockBackendClient
from agents.mocks.mock_groq import MockGroqClient
from agents.services.audit_service import ToolBudget, ToolBudgetExceeded

def runner(services, llm):
    return InvestigationRunner(MockBackendClient(services.persistence.db),services.rag,llm,services.persistence)

def test_real_graph_sequence(services,message):
    result=services.runner.run(message)
    assert result['execution_status']=='completed'
    assert [r['agent_name'] for r in result['agent_execution_trace']]==['transaction','retrieval','evidence','information_gap','report','verify']
    assert result['verification']['passed']

@pytest.mark.parametrize('always_fail,status', [(False,'completed'),(True,'incomplete')])
def test_single_correction(services,message,always_fail,status):
    llm=MockGroqClient(fail_first=True,always_fail=always_fail)
    result=runner(services,llm).run(message)
    assert result['execution_status']==status
    assert [r['agent_name'] for r in result['agent_execution_trace']][-2:]==['correction','reverify']
    assert len(llm.calls)==2
    assert any(a['event_type']=='verification' and not a['details']['passed'] for a in result['audit_history'])

def test_failure_persisted(services,message):
    class Broken:
        def get_alert_context(self,alert_id): raise RuntimeError('secret-value')
    broken=InvestigationRunner(Broken(),services.rag,services.llm,services.persistence)
    with pytest.raises(InvestigationFailed): broken.run(message)
    result=services.persistence.get(message.investigation_id)
    assert result['execution_status']=='failed'
    assert 'secret-value' not in str(result)

def test_budget_exact_limit(services):
    budget=ToolBudget(services.persistence.db,'x')
    for _ in range(8): budget.consume('rag.search')
    with pytest.raises(ToolBudgetExceeded): budget.consume('rag.search')
    with pytest.raises(PermissionError): budget.consume('record_decision')

def test_invalid_structured_output_correction(services,message):
    class BadOnce(MockGroqClient):
        def generate_structured_response(self,system_prompt,user_input,response_schema):
            if not user_input['correction_requested']:
                return response_schema.model_validate({})
            return super().generate_structured_response(system_prompt,user_input,response_schema)
    result=runner(services,BadOnce()).run(message)
    assert result['execution_status']=='completed'
    assert result['agent_execution_trace'][4]['error_message']=='StructuredOutputValidationError'

def test_tool_budget_enforced_in_running_graph(services,message):
    from agents.services.audit_service import consume
    class Runaway(MockGroqClient):
        def generate_structured_response(self,*args):
            for _ in range(9): consume('llm.generate')
    with pytest.raises(InvestigationFailed): runner(services,Runaway()).run(message)
    with services.persistence.db.connect() as c:
        assert c.execute('SELECT count(*) FROM tool_calls').fetchone()[0]==8
    assert services.persistence.get(message.investigation_id)['execution_status']=='failed'

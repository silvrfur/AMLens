from agents.schemas.messages import InvestigationMessage
from agents.worker.message_handler import MessageHandler
from agents.worker.service_bus_worker import drain_mock

def test_offline_end_to_end(services,message,monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.delenv('AZURE_SERVICE_BUS_CONNECTION_STRING',raising=False)
    services.bus.send(message)
    assert drain_mock(services.bus,MessageHandler(services.runner))==['completed']
    result=services.persistence.get(message.investigation_id)
    assert result['verification']['passed']
    assert result['report']['transaction_analysis']['computed_statistics']['USD.total']=='57400.00'
    assert result['audit_history'][-1]['event_type']=='persisted'
    with services.persistence.db.connect() as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('SELECT COUNT(*) FROM investigations').fetchone()[0]==1

def test_no_guidance_baseline(services):
    result=services.runner.run(InvestigationMessage(alert_id='ALT-002',investigation_id='BASELINE'))
    assert result['execution_status']=='completed'
    assert not result['report']['aml_guidance_and_evidence']['references']
    assert 'No retrieved guidance available' in result['verification']['warnings']

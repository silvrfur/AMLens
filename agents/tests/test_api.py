from fastapi.testclient import TestClient
from agents.main import create_app
from agents.worker.service_bus_worker import drain_mock
from agents.worker.message_handler import MessageHandler

def test_api_run_get_health(services,message):
    with TestClient(create_app(services=services)) as client:
        assert client.get('/health').json()['status']=='ok'
        result=client.post('/investigations/run',json=message.model_dump())
        assert result.status_code==200 and result.json()['verification']['passed']
        assert client.get('/investigations/'+message.investigation_id).json()['report']==result.json()['report']
        assert client.get('/investigations/unknown').status_code==404

def test_api_queue_and_validation(services,message):
    with TestClient(create_app(services=services)) as client:
        assert client.post('/investigations/queue',json=message.model_dump()).status_code==202
        assert drain_mock(services.bus,MessageHandler(services.runner))==['completed']
        assert client.post('/investigations/run',json={'alert_id':'x'}).status_code==422
        assert client.post('/investigations/run',json={**message.model_dump(),'decision':'close'}).status_code==422
        assert client.post('/investigations/run',json={**message.model_dump(),'alert_id':'ALT-002'}).status_code==409

def test_missing_alert_failure(services):
    with TestClient(create_app(services=services)) as client:
        assert client.post('/investigations/run',json={'alert_id':'MISSING','investigation_id':'MISSING'}).status_code==503

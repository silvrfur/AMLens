"""End-to-end API flow against PostgreSQL: upload -> alerts -> case -> mock
agent run -> human decision -> audit trail."""
import pytest

pytest.importorskip('agents', reason='agents package (member3-agents) not on PYTHONPATH')

HEADER = ('Timestamp,From Bank,Account,To Bank,Account.1,Amount Received,Receiving Currency,'
          'Amount Paid,Payment Currency,Payment Format,Is Laundering\n')
CSV = HEADER + '2022-09-01 10:00:00,001,A,002,B,1200000,US Dollar,1200000,US Dollar,ACH,1\n'


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def _upload(client, csv=CSV):
    return client.post('/upload-transactions', files={'file': ('sample.csv', csv, 'text/csv')})


def test_upload_and_alert_and_investigation(client):
    response = _upload(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['accepted'] == 1 and body['alerts_created'] == 1
    assert body['ground_truth_exposed'] is False

    page = client.get('/alerts').json()
    assert page['total'] == 1 and page['limit'] == 50 and page['offset'] == 0
    alerts = page['items']
    assert len(alerts) == 1
    assert alerts[0]['created_at']                       # frontend shows it
    assert alerts[0]['rule_id'] == 'HIGH_VALUE'
    assert isinstance(alerts[0]['evidence'], dict)       # JSONB round-trip
    assert all('Is Laundering' not in a and 'ground_truth' not in a for a in alerts)
    assert client.get('/alerts/' + alerts[0]['id']).status_code == 200

    inv = client.post('/investigate/' + alerts[0]['id'])
    assert inv.status_code == 201
    iid = inv.json()['investigation_id']

    # No AI report yet -> a review decision is refused.
    early = client.post(f'/investigations/{iid}/decision', json={
        'decision': 'ESCALATE', 'rationale': 'Needs additional supporting evidence.',
        'analyst_id': 'test-analyst'})
    assert early.status_code == 409

    # Mock agents read the alert from PostgreSQL through TeamBackend.
    run = client.post(f'/investigations/{iid}/run')
    assert run.status_code == 200, run.text
    assert run.json()['execution_status'] in ('completed', 'incomplete')

    detail = client.get(f'/investigations/{iid}').json()
    assert detail['rule_id'] == 'HIGH_VALUE'
    assert detail['execution_status'] == run.json()['execution_status']
    assert detail['created_at'] and detail['decision'] is None

    listed = client.get('/investigations').json()
    assert [i['investigation_id'] for i in listed] == [iid]
    assert listed[0]['execution_status'] == detail['execution_status']

    decision = client.post(f'/investigations/{iid}/decision', json={
        'decision': 'ESCALATE', 'rationale': 'Needs additional supporting evidence.',
        'analyst_id': 'test-analyst'})
    assert decision.status_code == 200, decision.text
    assert decision.json()['status'] == 'ESCALATE'
    assert decision.json()['decision'] == 'ESCALATE' and decision.json()['created_at']
    assert client.get(f'/investigations/{iid}').json()['decision']['analyst_id'] == 'test-analyst'

    audit = client.get(f'/audit/{iid}').json()
    assert [e['action'] for e in audit] == [
        'CREATED', 'AGENT_RUN_REQUESTED', 'AGENT_RUN_FINISHED', 'DECISION_RECORDED']


def test_duplicate_upload_rejected(client):
    assert _upload(client).status_code == 200
    again = _upload(client)
    assert again.status_code == 400
    assert 'already imported' in again.json()['detail']


def test_account_history_uses_tokens_and_exact_amounts(client):
    csv = HEADER + '2022-09-01 10:00:00,001,A,002,B,100.12345678,Euro,100.12345678,Euro,ACH,0\n'
    assert _upload(client, csv).status_code == 200
    assert client.get('/alerts').json()['items'] == []
    from app.utils.tokenization import account_token
    history = client.get(f"/accounts/{account_token('001', 'A')}/history").json()
    assert len(history) == 1
    assert history[0]['amount_paid'] == '100.12345678'       # NUMERIC, no float drift
    assert history[0]['timestamp'] == '2022-09-01T10:00:00'


def test_pending_investigation_has_stable_shape(client):
    assert _upload(client).status_code == 200
    alert_id = client.get('/alerts').json()['items'][0]['id']
    iid = client.post('/investigate/' + alert_id).json()['investigation_id']
    [case] = client.get('/investigations').json()
    assert case['investigation_id'] == iid and case['execution_status'] == 'pending'
    assert case['verification'] == {'passed': False, 'errors': [], 'warnings': []}
    assert client.get('/investigations?limit=0').status_code == 400


def test_health_reports_each_service(client, monkeypatch):
    monkeypatch.setenv('USE_MOCK_RAG', 'true')
    body = client.get('/health').json()
    assert body['status'] == 'ok' and body['backend'] == 'healthy' and body['agent'] == 'healthy'
    assert body['rag'] == 'degraded' and body['checked_at']
    assert body['queue'] == 'not_applicable'

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

    alerts = client.get('/alerts').json()
    assert len(alerts) == 1
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

    decision = client.post(f'/investigations/{iid}/decision', json={
        'decision': 'ESCALATE', 'rationale': 'Needs additional supporting evidence.',
        'analyst_id': 'test-analyst'})
    assert decision.status_code == 200, decision.text
    assert decision.json()['status'] == 'ESCALATE'

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
    alerts = client.get('/alerts').json()
    assert alerts == []
    from app.utils.tokenization import account_token
    history = client.get(f"/accounts/{account_token('001', 'A')}/history").json()
    assert len(history) == 1
    assert history[0]['amount_paid'] == '100.12345678'       # NUMERIC, no float drift
    assert history[0]['timestamp'] == '2022-09-01T10:00:00'

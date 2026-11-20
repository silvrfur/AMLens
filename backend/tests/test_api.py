import os
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['TOKEN_SECRET'] = 'test-secret-should-be-changed-before-prod-123456789'
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from app.database.connection import engine, Base
from app.main import app

# SQLite in-memory shared across TestClient connections
engine.dispose()
engine.pool = StaticPool(creator=lambda: __import__('sqlite3').connect(':memory:', check_same_thread=False))
Base.metadata.create_all(engine)
client = TestClient(app)

def test_upload_and_alert_and_investigation():
    csv = ('Timestamp,From Bank,Account,To Bank,Account.1,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering\n'
           '2022-09-01 10:00:00,001,A,002,B,1200000,US Dollar,1200000,US Dollar,ACH,1\n')
    response = client.post('/upload-transactions',files={'file':('sample.csv',csv,'text/csv')})
    assert response.status_code == 200, response.text
    assert response.json()['accepted'] == 1
    alerts = client.get('/alerts').json()
    assert len(alerts) == 1
    assert all('Is Laundering' not in a and 'ground_truth' not in a for a in alerts)
    inv = client.post('/investigate/'+alerts[0]['id'])
    assert inv.status_code == 201
    iid = inv.json()['investigation_id']
    decision = client.post('/investigations/'+iid+'/decision',json={
        'decision':'ESCALATE','rationale':'Needs additional supporting evidence.', 'analyst_id':'test-analyst'})
    assert decision.status_code == 200
    assert len(client.get('/audit/'+iid).json()) == 2

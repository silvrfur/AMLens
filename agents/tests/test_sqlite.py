import sqlite3
import pytest
from concurrent.futures import ThreadPoolExecutor
from agents.mocks.mock_backend import MockBackendClient
from agents.services.persistence import InvestigationBusy, InvestigationConflict, LostLease
from agents.schemas.messages import InvestigationMessage

def test_parameterized_read(services):
    backend=MockBackendClient(services.persistence.db)
    with pytest.raises(KeyError): backend.get_alert_context("' OR 1=1 --")
    assert len(backend.get_alert_context('ALT-001').transactions)==5

def test_transaction_rolls_back(services):
    with pytest.raises(RuntimeError):
        with services.persistence.db.connect() as c:
            c.execute("UPDATE alerts SET status='modified'")
            raise RuntimeError()
    with services.persistence.db.connect() as c:
        assert c.execute('SELECT status FROM alerts LIMIT 1').fetchone()[0]=='open'

def test_conflict_and_busy(services,message):
    services.persistence.claim(message)
    with pytest.raises(InvestigationBusy): services.persistence.claim(message)
    with pytest.raises(InvestigationConflict): services.persistence.claim(InvestigationMessage(alert_id='ALT-002',investigation_id=message.investigation_id))

def test_concurrent_claim_has_single_owner(services,message):
    def claim(_):
        try: return services.persistence.claim(message)
        except InvestigationBusy: return None
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(claim,range(4)))
    assert sum(r is not None for r in results)==1

def test_expired_lease_fences_old_writer(services,message):
    owner=services.persistence.claim(message)
    with services.persistence.db.connect() as c:
        c.execute('UPDATE investigations SET lease_until=0')
    new_owner=services.persistence.claim(message)
    assert owner!=new_owner
    with pytest.raises(LostLease): services.persistence.save({**message.model_dump(),'lease_owner':owner,'execution_status':'failed'})

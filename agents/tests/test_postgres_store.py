"""Agent runtime store on PostgreSQL (the deployment configuration).

Runs only when AML_AGENT_TEST_DATABASE_URL points at a throwaway database whose
name contains "test" (its agent_runtime schema is dropped), e.g. the docker one:
    AML_AGENT_TEST_DATABASE_URL=postgresql://amlens:amlens_dev@127.0.0.1:5433/amlens_test
"""
import os
import time

import pytest

from agents.config import Settings
from agents.main import create_services
from agents.schemas.messages import InvestigationMessage
from agents.services.persistence import InvestigationBusy, InvestigationConflict

URL = os.getenv('AML_AGENT_TEST_DATABASE_URL', '')
pytestmark = pytest.mark.skipif('test' not in URL.rsplit('/', 1)[-1],
                                reason='set AML_AGENT_TEST_DATABASE_URL to a *test* PostgreSQL database')


@pytest.fixture
def pg_services(tmp_path):
    import psycopg
    from agents.services import postgres_service
    from agents.services.sqlite_service import SQLiteService
    from agents.mocks.mock_backend import MockBackendClient
    with psycopg.connect(postgres_service.normalize_url(URL), autocommit=True) as c:
        c.execute('DROP SCHEMA IF EXISTS agent_runtime CASCADE')
    postgres_service._READY.clear()
    settings = Settings(_env_file=None, database_url=URL, use_mock_llm=True, use_mock_rag=True,
                        use_mock_backend=False, use_mock_service_bus=True)
    # Source alerts come from the SQLite fixtures (in deployment: the backend's TeamBackend);
    # only the agents' runtime store is PostgreSQL here.
    fixtures = MockBackendClient(SQLiteService(tmp_path / 'fixtures.db'))
    svc = create_services(settings, backend=fixtures)
    yield svc
    svc.close()


def test_full_run_persists_report_trace_and_audit(pg_services):
    result = pg_services.runner.run(InvestigationMessage(alert_id='ALT-001', investigation_id='INV-PG-1'))
    assert result['execution_status'] == 'completed'

    stored = pg_services.persistence.get('INV-PG-1')
    assert stored['execution_status'] == 'completed'
    assert stored['report']['alert_summary']['alert_id'] == 'ALT-001'
    names = [r['agent_name'] for r in stored['agent_execution_trace']]
    assert names[0] == 'transaction' and names[-1] == 'verify'   # insertion order kept
    assert stored['audit_history'][-1]['event_type'] == 'persisted'


def test_completed_run_is_not_repeated_and_conflicts_rejected(pg_services):
    msg = InvestigationMessage(alert_id='ALT-001', investigation_id='INV-PG-2')
    pg_services.runner.run(msg)
    assert pg_services.persistence.claim(msg) is None
    with pytest.raises(InvestigationConflict):
        pg_services.persistence.claim(InvestigationMessage(alert_id='ALT-OTHER', investigation_id='INV-PG-2'))


def test_live_lease_blocks_second_claim(pg_services):
    msg = InvestigationMessage(alert_id='ALT-001', investigation_id='INV-PG-3')
    assert pg_services.persistence.claim(msg)
    with pytest.raises(InvestigationBusy):
        pg_services.persistence.claim(msg)
    with pg_services.persistence.db.connect() as c:
        row = c.execute('SELECT lease_until FROM investigations WHERE investigation_id=?', ('INV-PG-3',)).fetchone()
    assert row['lease_until'] > time.time()

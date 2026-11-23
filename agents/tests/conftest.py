import pytest
from agents.config import Settings
from agents.main import create_services
from agents.schemas.messages import InvestigationMessage
from agents.agents.transaction_agent import TransactionAgent
from agents.agents.aml_retrieval_agent import AMLRetrievalAgent
from agents.agents.evidence_agent import EvidenceAgent
from agents.agents.information_gap_agent import InformationGapAgent
from agents.mocks.mock_backend import MockBackendClient

@pytest.fixture
def services(tmp_path):
    settings = Settings(_env_file=None, database_url=f'sqlite:///{tmp_path}/test.db',
        use_mock_llm=True, use_mock_rag=True, use_mock_backend=True, use_mock_service_bus=True)
    svc = create_services(settings)
    yield svc
    svc.close()

@pytest.fixture
def message(): return InvestigationMessage(alert_id='ALT-001', investigation_id='INV-TEST')

@pytest.fixture
def state(services, message):
    state = {**message.model_dump(), 'retry_count': 0}
    state.update(TransactionAgent(MockBackendClient(services.persistence.db))(state))
    state.update(AMLRetrievalAgent(services.rag)(state))
    state.update(EvidenceAgent()(state))
    state.update(InformationGapAgent()(state))
    return state

@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    import socket
    real_connect = socket.socket.connect
    def blocked(*args, **kwargs):
        raise AssertionError('Offline tests must not connect to external services')
    def connect(sock, address):
        # Windows asyncio builds its self-pipe with a loopback socketpair; allow only that.
        if isinstance(address, tuple) and address[0] == '127.0.0.1': return real_connect(sock, address)
        blocked()
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket.socket, 'connect', connect)

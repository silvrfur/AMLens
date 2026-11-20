from contextlib import asynccontextmanager
from dataclasses import dataclass
from fastapi import FastAPI
from .config import Settings
from .services.sqlite_service import SQLiteService
from .services.persistence import Persistence
from .services.backend_client import SQLiteBackendClient
from .services.groq_llm import GroqLLM
from .services.rag_client import HTTPRAGClient
from .services.service_bus import MockServiceBus, AzureServiceBus
from .mocks.mock_backend import MockBackendClient
from .mocks.mock_groq import MockGroqClient
from .mocks.mock_rag import MockRAGClient
from .graph import InvestigationRunner
from .api.routes import router

@dataclass
class Services:
    runner: InvestigationRunner
    persistence: Persistence
    bus: object
    llm: object
    rag: object
    def close(self):
        self.bus.close()
        if hasattr(self.rag, 'close'): self.rag.close()
        if isinstance(self.llm, GroqLLM): self.llm.client.close()

def create_services(settings=None, *, backend=None, rag=None, llm=None, bus=None):
    settings = settings or Settings()
    if settings.llm_provider != 'groq': raise ValueError('Only Groq is supported')
    db = SQLiteService(settings.database_path)
    persistence = Persistence(db, settings.lease_seconds)
    backend = backend or (MockBackendClient(db) if settings.use_mock_backend else SQLiteBackendClient(db))
    if rag is None:
        if settings.use_mock_rag: rag = MockRAGClient()
        elif settings.rag_service_url: rag = HTTPRAGClient(settings.rag_service_url)
        else: raise ValueError('Configure RAG_SERVICE_URL or inject Member 2 adapter')
    llm = llm or (MockGroqClient() if settings.use_mock_llm else GroqLLM(settings.groq_api_key, settings.groq_model, settings.groq_timeout_seconds))
    bus = bus or (MockServiceBus() if settings.use_mock_service_bus else AzureServiceBus(settings.azure_service_bus_connection_string, settings.azure_service_bus_queue_name))
    return Services(InvestigationRunner(backend, rag, llm, persistence), persistence, bus, llm, rag)

def create_app(settings=None, services=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.services = services or create_services(settings)
        yield
        app.state.services.close()
    app = FastAPI(title='AMLens / TraceIQ Investigation Assistant', lifespan=lifespan)
    app.include_router(router)
    return app

app = create_app()

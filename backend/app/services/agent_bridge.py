"""Local development bridge to the agent team's independent persistence database.

The source Member 1 database is never passed as the agent persistence database.
No service bus or live LLM is required for the local smoke test.
"""
import os
from pathlib import Path

from agents.config import Settings
from agents.main import create_services
from agents.services.sqlite_service import SQLiteService
from agents.services.persistence import Persistence
from app.integrations.team_backend import TeamBackend


def _source_path() -> Path:
    explicit = os.getenv('AML_SOURCE_DATABASE_PATH')
    if explicit:
        return Path(explicit).expanduser().resolve()
    source_url = os.getenv('DATABASE_URL', 'sqlite:///./aml.db')
    if not source_url.startswith('sqlite:///'):
        raise ValueError('Local agent bridge requires a SQLite source database')
    return Path(source_url.removeprefix('sqlite:///')).resolve()


def _agent_path() -> Path:
    return Path(os.getenv('AML_AGENT_DATABASE_PATH', './agent_runtime.db')).expanduser().resolve()


def get_agent_persistence():
    """Retrieve persisted reports without starting an investigation."""
    path = _agent_path()
    if path == _source_path():
        raise ValueError('Agent persistence must not share Member 1 source SQLite file')
    return Persistence(SQLiteService(path))


def get_agent_services():
    """Create a short-lived set of local mock agent services for a synchronous run."""
    source, agent = _source_path(), _agent_path()
    if source == agent:
        raise ValueError('Agent persistence must not share Member 1 source SQLite file')
    zone = os.getenv('AML_SOURCE_TIMEZONE')
    if not zone:
        raise ValueError('Set AML_SOURCE_TIMEZONE explicitly for source transaction timestamps')
    backend = TeamBackend(database_path=str(source), source_timezone=zone,
                          window_hours=48, max_transactions=200, timeout_seconds=3)
    settings = Settings(
        _env_file=None,
        database_url='sqlite:///' + agent.as_posix(),
        use_mock_backend=False,
        use_mock_llm=True,
        use_mock_rag=True,
        use_mock_service_bus=True,
        llm_provider='groq',
    )
    return create_services(settings=settings, backend=backend)

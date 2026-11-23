"""Local development bridge to the agent team's independent persistence database.

Two databases, never the same one:
- Member 1 source data (transactions, alerts, cases): PostgreSQL, read by
  TeamBackend through READ ONLY transactions.
- Agent runtime persistence (reports, agent runs, tool calls): the agents
  package's own SQLite file (agent_runtime.db), unchanged.

No service bus or live LLM is required for the local smoke test.
"""
import os
from pathlib import Path

from agents.config import Settings
from agents.main import create_services
from agents.services.sqlite_service import SQLiteService
from agents.services.persistence import Persistence
from app.database.connection import normalize_database_url
from app.integrations.team_backend import TeamBackend

_BACKENDS: dict[tuple[str, str], TeamBackend] = {}


def _source_url() -> str:
    """PostgreSQL URL the agent adapter reads from.

    AML_SOURCE_DATABASE_URL lets you use a SELECT-only login for the agents;
    otherwise the main DATABASE_URL is used (reads are READ ONLY regardless).
    """
    url = os.getenv('AML_SOURCE_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('Set DATABASE_URL (or AML_SOURCE_DATABASE_URL) for the Member 1 source database')
    return normalize_database_url(url)


def _agent_path() -> Path:
    path = Path(os.getenv('AML_AGENT_DATABASE_PATH', './agent_runtime.db')).expanduser().resolve()
    if path.suffix.lower() not in ('.db', '.sqlite', '.sqlite3'):
        raise ValueError('AML_AGENT_DATABASE_PATH must point to the agents SQLite file (e.g. agent_runtime.db)')
    return path


def _team_backend(zone: str) -> TeamBackend:
    """One adapter (and connection pool) per process, reused across runs."""
    key = (_source_url(), zone)
    if key not in _BACKENDS:
        _BACKENDS[key] = TeamBackend(database_url=key[0], source_timezone=zone,
                                     window_hours=48, max_transactions=200, timeout_seconds=3)
    return _BACKENDS[key]


def get_agent_persistence():
    """Retrieve persisted reports without starting an investigation."""
    return Persistence(SQLiteService(_agent_path()))


def get_agent_services():
    """Create a short-lived set of local mock agent services for a synchronous run."""
    agent = _agent_path()
    zone = os.getenv('AML_SOURCE_TIMEZONE')
    if not zone:
        raise ValueError('Set AML_SOURCE_TIMEZONE explicitly for source transaction timestamps')
    settings = Settings(
        _env_file=None,
        database_url='sqlite:///' + agent.as_posix(),
        use_mock_backend=False,
        use_mock_llm=True,
        use_mock_rag=True,
        use_mock_service_bus=True,
        llm_provider='groq',
    )
    return create_services(settings=settings, backend=_team_backend(zone))

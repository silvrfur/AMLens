"""Local development bridge to the agent team's independent persistence database.

Two databases, never the same one:
- Member 1 source data (transactions, alerts, cases): PostgreSQL, read by
  TeamBackend through READ ONLY transactions.
- Agent runtime persistence (reports, agent runs, tool calls): either
  PostgreSQL (AML_AGENT_DATABASE_URL, schema `agent_runtime`; use this in any
  deployment, since container disks are wiped on restart) or the agents' own
  SQLite file (AML_AGENT_DATABASE_PATH, default ./agent_runtime.db) locally.

LLM and RAG come from the environment (backend/.env is loaded by
app.database.connection): USE_MOCK_LLM, LLM_PROVIDER, AZURE_OPENAI_*,
USE_MOCK_RAG, RAG_SERVICE_URL. Both default to the offline mocks, so no live
LLM, RAG or service bus is required for the local smoke test.
"""
import os
from pathlib import Path

from agents.config import Settings
from agents.main import create_services, create_store
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


def _agent_database_url() -> str:
    """Where agent runs are stored: AML_AGENT_DATABASE_URL (PostgreSQL), else the SQLite file."""
    url = os.getenv('AML_AGENT_DATABASE_URL', '').strip()
    if url:
        if not url.startswith(('postgresql://', 'postgresql+psycopg://', 'postgres://')):
            raise ValueError('AML_AGENT_DATABASE_URL must be a PostgreSQL URL')
        return url
    return 'sqlite:///' + _agent_path().as_posix()


def _agent_settings(**overrides) -> Settings:
    return Settings(_env_file=None, database_url=_agent_database_url(), **overrides)


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
    return Persistence(create_store(_agent_settings()))


def get_agent_services():
    """Create a short-lived set of agent services for a synchronous run.

    The bridge pins only what it owns: the agents' runtime store, the real
    PostgreSQL backend adapter and the in-process queue. LLM/RAG settings are
    read from environment variables by agents.config.Settings.
    """
    zone = os.getenv('AML_SOURCE_TIMEZONE')
    if not zone:
        raise ValueError('Set AML_SOURCE_TIMEZONE explicitly for source transaction timestamps')
    settings = _agent_settings(use_mock_backend=False, use_mock_service_bus=True)
    return create_services(settings=settings, backend=_team_backend(zone))

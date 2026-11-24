"""Service health for the frontend status panel.

Each service is "healthy", "degraded" (running on a local stand-in) or "offline".
"""
import importlib.util
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.database.connection import engine

router = APIRouter()


def _flag(name: str) -> bool:
    return os.getenv(name, 'true').strip().lower() not in ('false', '0', 'no')


def _backend() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return 'healthy'
    except Exception:
        return 'offline'


def _agent() -> str:
    return 'healthy' if importlib.util.find_spec('agents') else 'offline'


def _rag() -> str:
    if _flag('USE_MOCK_RAG'):
        return 'degraded'  # offline fixtures, not the approved guidance corpus
    url = os.getenv('RAG_SERVICE_URL', '').rstrip('/')
    if not url:
        return 'offline'
    try:
        return 'healthy' if httpx.get(url + '/', timeout=2).status_code == 200 else 'offline'
    except httpx.HTTPError:
        return 'offline'


@router.get('/health')
def health():
    return {
        'status': 'ok',
        'backend': _backend(),
        'agent': _agent(),
        'rag': _rag(),
        # Runs are synchronous through an in-process queue; Azure Service Bus
        # is not wired into the backend yet.
        'queue': 'degraded',
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }

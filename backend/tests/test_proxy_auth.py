"""The shared-secret check that lets only the frontend proxy call the API (app/security.py)."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.security import require_proxy


@pytest.fixture
def client():
    app = FastAPI()
    app.middleware('http')(require_proxy)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/whoami')
    def whoami(request: Request):
        return {'user': request.state.user}

    return TestClient(app)


def test_open_when_no_key_configured(client, monkeypatch):
    monkeypatch.delenv('AML_PROXY_KEY', raising=False)
    r = client.get('/whoami', headers={'X-AMLens-User': 'spoofed@example.com'})
    assert r.status_code == 200
    assert r.json() == {'user': None}   # identity header is ignored without the key check


def test_rejects_missing_or_wrong_key(client, monkeypatch):
    monkeypatch.setenv('AML_PROXY_KEY', 'k' * 40)
    assert client.get('/whoami').status_code == 401
    assert client.get('/whoami', headers={'X-AMLens-Proxy-Key': 'wrong'}).status_code == 401


def test_accepts_proxy_and_trusts_its_user(client, monkeypatch):
    monkeypatch.setenv('AML_PROXY_KEY', 'k' * 40)
    r = client.get('/whoami', headers={'X-AMLens-Proxy-Key': 'k' * 40, 'X-AMLens-User': 'analyst@bank.example'})
    assert r.status_code == 200
    assert r.json() == {'user': 'analyst@bank.example'}


def test_health_stays_open_for_probes(client, monkeypatch):
    monkeypatch.setenv('AML_PROXY_KEY', 'k' * 40)
    assert client.get('/health').status_code == 200

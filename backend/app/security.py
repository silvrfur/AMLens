"""Only accept API calls that came through the frontend's server-side proxy.

In a deployment the browser never talks to this API directly: it calls the
frontend's /api/backend/* route, which sits behind Entra ID sign-in (Azure
Container Apps authentication) and forwards the request here with

    X-AMLens-Proxy-Key: <AML_PROXY_KEY>       shared secret, proves it is the proxy
    X-AMLens-User:      <signed-in user>      from Easy Auth's principal header

Set AML_PROXY_KEY (same value on the frontend and the backend) to switch the
check on. Unset = local development: every request is accepted, as before.
/health stays open so platform probes work.
"""
import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

OPEN_PATHS = {'/health'}


def _proxy_key() -> str:
    return os.getenv('AML_PROXY_KEY', '').strip()


async def require_proxy(request: Request, call_next):
    request.state.user = None
    key = _proxy_key()
    if key and request.url.path not in OPEN_PATHS and request.method != 'OPTIONS':
        sent = request.headers.get('x-amlens-proxy-key', '')
        if not hmac.compare_digest(sent.encode(), key.encode()):
            return JSONResponse({'detail': 'Not authenticated'}, status_code=401)
        # Trusted only because the shared secret matched.
        request.state.user = request.headers.get('x-amlens-user') or None
    return await call_next(request)

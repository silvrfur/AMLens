import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.connection import engine
from app.database import tables  # noqa: F401; registers ORM models
from app.database.schema_check import assert_schema_current
from app.api import upload, alerts, transactions, investigations, health
from app.security import require_proxy


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Tables are managed by Alembic (`alembic upgrade head`), not created here.
    assert_schema_current(engine)
    yield
    engine.dispose()


app = FastAPI(title='AML Member 1 Backend (MVP)', version='0.3.0', lifespan=lifespan)

# Proxy check (see app/security.py). Registered before CORS, so CORS is the outer
# layer and a 401 still carries CORS headers for local cross-origin development.
app.middleware('http')(require_proxy)

# Allow only explicitly configured local frontend origins. Never use '*'.
allowed_origins = [origin.strip() for origin in os.getenv('AML_CORS_ORIGINS', '').split(',') if origin.strip()]
if allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                       allow_credentials=False, allow_methods=['GET', 'POST'],
                       allow_headers=['Content-Type', 'Authorization'])
app.include_router(upload.router, tags=['Uploads'])
app.include_router(alerts.router, tags=['Alerts'])
app.include_router(transactions.router, tags=['Transactions'])
app.include_router(investigations.router, tags=['Investigations'])
app.include_router(health.router, tags=['Health'])

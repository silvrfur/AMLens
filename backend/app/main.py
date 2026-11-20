import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.connection import Base, engine
from app.database import tables  # noqa: F401; registers ORM models
from app.api import upload, alerts, transactions, investigations

app = FastAPI(title='AML Member 1 Backend (MVP)', version='0.2.0')

# Allow only explicitly configured local frontend origins. Never use '*'.
allowed_origins = [origin.strip() for origin in os.getenv('AML_CORS_ORIGINS', '').split(',') if origin.strip()]
if allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                       allow_credentials=False, allow_methods=['GET', 'POST'],
                       allow_headers=['Content-Type', 'Authorization'])
Base.metadata.create_all(bind=engine)  # Dev only; use Alembic migrations later
app.include_router(upload.router, tags=['Uploads'])
app.include_router(alerts.router, tags=['Alerts'])
app.include_router(transactions.router, tags=['Transactions'])
app.include_router(investigations.router, tags=['Investigations'])

@app.get('/health')
def health():
    return {'status':'ok'}

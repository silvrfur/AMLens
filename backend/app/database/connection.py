"""PostgreSQL connection for the main AML data (transactions, alerts, cases, audit).

The agent team's runtime database (agent_runtime.db) is NOT configured here;
it stays a separate SQLite file owned by the agents package (see agent_bridge).
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Read backend/.env if present. Real environment variables always win.
load_dotenv()


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL that uses the psycopg (v3) PostgreSQL driver.

    Accepts the common forms postgres://, postgresql:// and
    postgresql+psycopg://. Anything else (including SQLite) is rejected so the
    main AML data can never silently fall back to a local file.
    """
    url = (url or '').strip()
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url.removeprefix('postgres://')
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url.removeprefix('postgresql://')
    if not url.startswith('postgresql+psycopg://'):
        raise RuntimeError(
            'DATABASE_URL must be a PostgreSQL URL, e.g. '
            'postgresql+psycopg://amlens:password@localhost:5432/amlens '
            '(see backend/.env.example)')
    return url


def database_url() -> str:
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError(
            'DATABASE_URL is not set. Copy backend/.env.example to backend/.env '
            'and point it at your PostgreSQL database.')
    return normalize_database_url(url)


DATABASE_URL = database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # drop dead connections (Azure closes idle ones)
    pool_size=int(os.getenv('DB_POOL_SIZE', '5')),
    max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '10')),
    pool_recycle=1800,
    # Sessions run in UTC so timestamptz values come back as +00:00 whatever
    # the server's default TimeZone is.
    connect_args={'connect_timeout': 10, 'application_name': 'amlens-backend',
                  'options': '-c timezone=UTC'},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db

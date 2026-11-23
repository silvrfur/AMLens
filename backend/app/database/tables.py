"""ORM models for the main AML data, stored in PostgreSQL.

Schema changes must go through an Alembic migration (backend/alembic/versions).
Table and column names are part of the contract with the frontend API and the
agent adapter (app/integrations/team_backend.py) - do not rename casually.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, Integer, DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


def now():
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    # IBM source timestamps carry no timezone; AML_SOURCE_TIMEZONE says which
    # zone they are in, so this column is deliberately timezone-naive.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    sender_token: Mapped[str] = mapped_column(String(36), index=True)
    receiver_token: Mapped[str] = mapped_column(String(36), index=True)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    payment_currency: Mapped[str] = mapped_column(String(40))
    amount_received: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    receiving_currency: Mapped[str] = mapped_column(String(40))
    payment_format: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint('dataset_id', 'source_row'),)


class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey('transactions.id'), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default='OPEN')
    # Nullable only to preserve legacy alerts created before this column
    # existed; the agent adapter refuses alerts without it.
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=now, nullable=True)


class Investigation(Base):
    __tablename__ = 'investigations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey('alerts.id'), index=True)
    status: Mapped[str] = mapped_column(String(32), default='PENDING_AGENT')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InvestigatorDecision(Base):
    __tablename__ = 'investigator_decisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey('investigations.id'), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    analyst_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReportVersion(Base):
    __tablename__ = 'report_versions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey('investigations.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = 'audit_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey('investigations.id'), index=True)
    action: Mapped[str] = mapped_column(String(70))
    details: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

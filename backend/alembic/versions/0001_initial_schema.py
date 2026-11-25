"""Initial PostgreSQL schema for the main AML data.

Mirrors the former SQLite aml.db schema (including alerts.created_at, which
replaces the old migrations/001_add_alert_created_at.py script), with
PostgreSQL types: JSONB for evidence/details and timestamptz for
system-generated timestamps.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transactions',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('dataset_id', sa.String(64), nullable=False),
        sa.Column('source_row', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=False), nullable=False),
        sa.Column('sender_token', sa.String(36), nullable=False),
        sa.Column('receiver_token', sa.String(36), nullable=False),
        sa.Column('amount_paid', sa.Numeric(24, 8), nullable=False),
        sa.Column('payment_currency', sa.String(40), nullable=False),
        sa.Column('amount_received', sa.Numeric(24, 8), nullable=False),
        sa.Column('receiving_currency', sa.String(40), nullable=False),
        sa.Column('payment_format', sa.String(40), nullable=False),
        sa.UniqueConstraint('dataset_id', 'source_row', name='transactions_dataset_id_source_row_key'),
    )
    op.create_index('ix_transactions_dataset_id', 'transactions', ['dataset_id'])
    op.create_index('ix_transactions_timestamp', 'transactions', ['timestamp'])
    op.create_index('ix_transactions_sender_token', 'transactions', ['sender_token'])
    op.create_index('ix_transactions_receiver_token', 'transactions', ['receiver_token'])

    op.create_table(
        'alerts',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('transaction_id', sa.String(80), sa.ForeignKey('transactions.id'), nullable=False),
        sa.Column('rule_id', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_alerts_transaction_id', 'alerts', ['transaction_id'])

    op.create_table(
        'investigations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('alert_id', sa.String(80), sa.ForeignKey('alerts.id'), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_investigations_alert_id', 'investigations', ['alert_id'])

    op.create_table(
        'investigator_decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('investigation_id', sa.String(36), sa.ForeignKey('investigations.id'), nullable=False),
        sa.Column('decision', sa.String(32), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('analyst_id', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_investigator_decisions_investigation_id', 'investigator_decisions', ['investigation_id'])

    op.create_table(
        'report_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('investigation_id', sa.String(36), sa.ForeignKey('investigations.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('report_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_report_versions_investigation_id', 'report_versions', ['investigation_id'])

    op.create_table(
        'audit_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('investigation_id', sa.String(36), sa.ForeignKey('investigations.id'), nullable=False),
        sa.Column('action', sa.String(70), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_history_investigation_id', 'audit_history', ['investigation_id'])


def downgrade() -> None:
    op.drop_table('audit_history')
    op.drop_table('report_versions')
    op.drop_table('investigator_decisions')
    op.drop_table('investigations')
    op.drop_table('alerts')
    op.drop_table('transactions')

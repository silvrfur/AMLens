"""Backfill alert statuses for alerts investigated or decided before the lifecycle existed.

The API now moves an alert OPEN -> UNDER REVIEW when an investigation is opened and
-> DECIDED when an investigator records a decision. Older rows stayed OPEN; this
brings them in line. Data-only; downgrade puts every alert back to OPEN as before.

Revision ID: 0002_alert_status
Revises: 0001_initial
Create Date: 2026-11-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0002_alert_status'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE alerts SET status = 'DECIDED'
        WHERE status <> 'DECIDED' AND id IN (
            SELECT i.alert_id FROM investigations i
            JOIN investigator_decisions d ON d.investigation_id = i.id)
    """)
    op.execute("""
        UPDATE alerts SET status = 'UNDER REVIEW'
        WHERE status = 'OPEN' AND id IN (SELECT alert_id FROM investigations)
    """)


def downgrade() -> None:
    op.execute("UPDATE alerts SET status = 'OPEN' WHERE status IN ('UNDER REVIEW', 'DECIDED')")

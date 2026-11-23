"""TeamBackend (agent adapter) against PostgreSQL."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip('agents', reason='agents package (member3-agents) not on PYTHONPATH')

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from app.integrations.team_backend import TeamBackend  # noqa: E402


def _tx(tid, dataset, ts, sender, receiver, amount):
    return dict(id=tid, dataset_id=dataset, source_row=int(tid.rsplit('-', 1)[-1].replace('OTHER', '99')),
                timestamp=datetime.fromisoformat(ts), sender_token=sender, receiver_token=receiver,
                amount_paid=Decimal(amount), payment_currency='US Dollar',
                amount_received=Decimal(amount), receiving_currency='US Dollar', payment_format='ACH')


@pytest.fixture
def seeded(clean_db):
    from app.database.tables import Transaction, Alert
    with clean_db.begin() as conn:
        conn.execute(Transaction.__table__.insert(), [
            _tx('TX-2', 'demo_dataset', '2022-09-01 10:00:00', 'ACC-A', 'ACC-B', '1200000.00000000'),
            _tx('TX-3', 'demo_dataset', '2022-09-01 10:15:00', 'ACC-B', 'ACC-C', '1180000.00000000'),
            # Same account, different dataset: must NOT appear in the bundle.
            _tx('TX-OTHER', 'other_dataset', '2022-09-01 10:10:00', 'ACC-X', 'ACC-B', '500000.00000000'),
            # Same dataset but outside the 48h window: must NOT appear.
            _tx('TX-9', 'demo_dataset', '2022-09-05 10:00:00', 'ACC-B', 'ACC-D', '10.00'),
        ])
        conn.execute(Alert.__table__.insert(), [dict(
            id='AL-3', transaction_id='TX-3', rule_id='RAPID_MOVEMENT_CANDIDATE',
            description='ignore untrusted desc', status='OPEN',
            evidence={'anchor_account_token': 'ACC-B', 'transaction_ids': ['TX-2', 'TX-3']},
            created_at=datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc))])
    backend = TeamBackend(source_timezone='UTC')
    yield backend
    backend.close()


def test_demo_bundle(seeded):
    bundle = seeded.get_alert_context('AL-3')

    assert bundle.alert.typology == 'rapid_movement'
    assert bundle.alert.status == 'open'
    # Same UTC string the SQLite adapter produced, whatever the server TimeZone.
    assert bundle.alert.created_at == '2026-11-20T06:00:00+00:00'

    ids = [tx.transaction_id for tx in bundle.transactions]
    assert ids == ['TX-2', 'TX-3']                       # other dataset + out-of-window excluded
    assert [tx.transaction_type for tx in bundle.transactions] == ['deposit', 'withdrawal']
    assert [tx.amount for tx in bundle.transactions] == [Decimal('1200000.00'), Decimal('1180000.00')]
    assert all(tx.timestamp.tzinfo is not None for tx in bundle.transactions)

    with pytest.raises(KeyError):
        seeded.get_alert_context('missing')


def test_history_limit_keeps_closest_transactions(seeded, clean_db):
    from app.database.tables import Transaction
    with clean_db.begin() as conn:
        conn.execute(Transaction.__table__.insert(), [
            _tx(f'TX-{n}', 'demo_dataset', f'2022-09-01 {h:02d}:00:00', 'ACC-B', 'ACC-E', '1.00')
            for n, h in ((10, 5), (11, 9), (12, 20))])
    backend = TeamBackend(source_timezone='UTC', max_transactions=3)
    try:
        ids = {tx.transaction_id for tx in backend.get_alert_context('AL-3').transactions}
    finally:
        backend.close()
    # Trigger + 2 closest in time (TX-2 at 10:00, TX-11 at 09:00); evidence kept.
    assert ids == {'TX-3', 'TX-2', 'TX-11'}


def test_adapter_transactions_are_read_only(seeded):
    with pytest.raises(DBAPIError, match='read-only transaction'):
        with seeded._read_only() as conn:
            conn.execute(text("UPDATE alerts SET status = 'CLOSED' WHERE id = 'AL-3'"))
    with seeded.engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM alerts WHERE id = 'AL-3'")).scalar() == 'OPEN'


def test_missing_created_at_is_rejected(seeded, clean_db):
    with clean_db.begin() as conn:
        conn.execute(text("UPDATE alerts SET created_at = NULL WHERE id = 'AL-3'"))
    with pytest.raises(ValueError, match='created_at'):
        seeded.get_alert_context('AL-3')

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.services.transaction_analysis import generate_findings


def _tx(tid, sender, receiver, minutes=0, amount="1500000"):
    return SimpleNamespace(
        id=tid,
        sender_token=sender,
        receiver_token=receiver,
        timestamp=datetime(2022, 9, 1, 10, 0) + timedelta(minutes=minutes),
        amount_paid=Decimal(amount),
        payment_currency="US Dollar",
        amount_received=Decimal(amount),
        receiving_currency="US Dollar",
    )


def test_self_transfers_never_produce_or_support_findings():
    rows = [
        # High-value self-transfer: must not raise HIGH_VALUE.
        _tx("SELF_HV", "A", "A"),
        # Repeated self-transfers: must not raise REPEATED_PAIR.
        *[_tx(f"SELF_{i}", "B", "B", minutes=i, amount="10") for i in range(6)],
        # Self-transfer as inbound leg followed by real outbound:
        # must not raise RAPID_MOVEMENT_CANDIDATE.
        _tx("SELF_IN", "C", "C", minutes=0, amount="10"),
        _tx("C_OUT", "C", "D", minutes=10, amount="10"),
    ]

    findings = generate_findings(rows)
    self_ids = {r.id for r in rows if r.sender_token == r.receiver_token}

    for f in findings:
        assert f["transaction_id"] not in self_ids
        assert not self_ids & set(f["evidence"]["transaction_ids"])


def test_normal_high_value_still_alerts():
    findings = generate_findings([_tx("T1", "A", "B")])
    assert [f["rule_id"] for f in findings] == ["HIGH_VALUE"]


def test_repeated_pair_only_counts_repeats_within_window():
    # 5 transfers spread over 5 days: never 5 within 48h -> no alert.
    spread = [
        _tx(f"S{i}", "A", "B", minutes=i * 24 * 60, amount="10")
        for i in range(5)
    ]
    assert not [
        f for f in generate_findings(spread)
        if f["rule_id"] == "REPEATED_PAIR"
    ]

    # 5 transfers within a few hours -> one alert, all evidence in window.
    burst = [
        _tx(f"B{i}", "A", "B", minutes=10 * 24 * 60 + i * 30, amount="10")
        for i in range(5)
    ]
    pair_findings = [
        f for f in generate_findings(spread + burst)
        if f["rule_id"] == "REPEATED_PAIR"
    ]
    assert len(pair_findings) == 1
    assert pair_findings[0]["evidence"]["transaction_ids"] == [
        f"B{i}" for i in range(5)
    ]

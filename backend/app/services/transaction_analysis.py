
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal


def generate_findings(
    rows,
    *,
    high_value_threshold=Decimal("1000000"),
    high_value_currency="US Dollar",
    repeated_min_count=5,
    repeated_window=timedelta(hours=48),
):
    """
    Generate deterministic AML review findings.

    No ground-truth labels are used.
    Findings are observations, not laundering conclusions.

    Self-transfers (sender_token == receiver_token, e.g. an account
    converting currency into itself) are excluded from every rule:
    they are not movement between parties, and the agent AlertBundle
    contract cannot represent them (it only has deposit/withdrawal).
    They remain stored in the transactions table unchanged.
    """

    rows = [
        tx for tx in rows
        if tx.sender_token != tx.receiver_token
    ]

    findings = []
    pairs = defaultdict(list)

    # RULE 1: HIGH VALUE
    for tx in rows:

        pairs[
            (
                tx.sender_token,
                tx.receiver_token,
                tx.payment_currency
            )
        ].append(tx)

        if (
            tx.payment_currency == high_value_currency
            and tx.amount_paid >= high_value_threshold
        ):

            findings.append({
                "rule_id": "HIGH_VALUE",
                "transaction_id": tx.id,
                "description": (
                    "Transaction meets configured "
                    "currency-specific review threshold; "
                    "not proof of laundering."
                ),
                "evidence": {
                    "transaction_ids": [tx.id],
                    "anchor_account_token": tx.sender_token,
                    "amount_paid": str(tx.amount_paid),
                    "currency": tx.payment_currency,
                    "threshold": str(high_value_threshold)
                }
            })

    # RULE 2: REPEATED ACCOUNT PAIRS (within a bounded time window)
    #
    # Repeats are counted only inside a window starting at the first
    # transaction of each burst, so every evidence transaction lies
    # within the history window the agent adapter loads around the
    # triggering transaction. Bursts do not overlap.
    for (sender, receiver, currency), txs in pairs.items():

        txs = sorted(txs, key=lambda t: (t.timestamp, t.id))
        i = 0

        while i < len(txs):

            j = i
            while (
                j + 1 < len(txs)
                and txs[j + 1].timestamp - txs[i].timestamp
                <= repeated_window
            ):
                j += 1

            burst = txs[i:j + 1]

            if len(burst) < repeated_min_count:
                i += 1
                continue

            ids = [t.id for t in burst]

            findings.append({
                "rule_id": "REPEATED_PAIR",
                "transaction_id": ids[0],
                "description": (
                    "Repeated transactions between "
                    "this account pair within "
                    f"{repeated_window}; context required."
                ),
                "evidence": {
                    "transaction_ids": ids,
                    "anchor_account_token": sender,
                    "sender_token": sender,
                    "receiver_token": receiver,
                    "currency": currency,
                    "count": len(ids),
                    "window_hours": (
                        repeated_window.total_seconds() / 3600
                    ),
                }
            })

            i = j + 1

    # RULE 3: RAPID MOVEMENT CANDIDATE
    incoming = defaultdict(list)
    outgoing = defaultdict(list)

    for tx in rows:

        incoming[
            (tx.receiver_token, tx.receiving_currency)
        ].append(tx)

        outgoing[
            (tx.sender_token, tx.payment_currency)
        ].append(tx)

    for key in incoming.keys() & outgoing.keys():

        for inc in incoming[key]:

            for out in outgoing[key]:

                minutes = (
                    out.timestamp - inc.timestamp
                ).total_seconds() / 60

                if 0 < minutes <= 60:

                    findings.append({
                        "rule_id": "RAPID_MOVEMENT_CANDIDATE",
                        "transaction_id": out.id,
                        "description": (
                            "Inbound and subsequent outbound "
                            "transactions observed at an "
                            "intermediary; fund identity "
                            "is unverified."
                        ),
                        "evidence": {
                            "transaction_ids": [
                                inc.id,
                                out.id
                            ],
                            "anchor_account_token": key[0],
                            "account_token": key[0],
                            "currency": key[1],
                            "gap_minutes": minutes,
                            "incoming_amount": str(
                                inc.amount_received
                            ),
                            "outgoing_amount": str(
                                out.amount_paid
                            )
                        }
                    })

                    if len(findings) >= 10000:
                        return findings

    return findings


"""Read-only Member 1 PostgreSQL -> Agent AlertBundle adapter.

Implements the agents package's BackendClient protocol
(agents/services/backend_client.py): get_alert_context(alert_id) -> AlertBundle.

Responsibilities:
- Read alerts and transactions from Member 1 PostgreSQL, inside
  READ ONLY transactions with a statement timeout.
- Convert backend records into the agent team's AlertBundle schema.
- Never write to source tables.
- Never expose ground-truth laundering labels or raw account references.
- Keep transactions within the alert's dataset and bounded history.
- Always include the alert's triggering transaction.
- Never discard required alert evidence.
- Exclude non-required self-transfers only under the documented MVP policy.
- Never invent case-verification metadata.

IMPORTANT:
The existing agent contract supports only "deposit" and "withdrawal".
Excluded self-transfers make the resulting history incomplete. This is
a local MVP compatibility policy, not a complete investigation policy.
"""

import json
import logging
import os

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from app.database.connection import normalize_database_url

from agents.schemas.investigation import AlertBundle
from agents.services.audit_service import consume


logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# 1. Map backend detection rules to agent typologies
# ----------------------------------------------------------

RULE_TO_TYPOLOGY = {
    "HIGH_VALUE": "unusual_activity",
    "REPEATED_PAIR": "unusual_activity",
    "RAPID_MOVEMENT_CANDIDATE": "rapid_movement",
    "FAN_IN": "fan_in_out",
    "FAN_OUT": "fan_in_out",
    "STRUCTURING_CANDIDATE": "structuring",
}


# ----------------------------------------------------------
# 2. Map IBM currency names to standard currency codes
# ----------------------------------------------------------

CURRENCIES = {
    "US Dollar": "USD",
    "Euro": "EUR",
    "Swiss Franc": "CHF",
    "Yuan": "CNY",
    "Shekel": "ILS",
    "Rupee": "INR",
    "UK Pound": "GBP",
    "Yen": "JPY",
    "Ruble": "RUB",
    "Canadian Dollar": "CAD",
    "Australian Dollar": "AUD",
    "Mexican Peso": "MXN",
    "Saudi Riyal": "SAR",
    "Brazil Real": "BRL",
}


# ----------------------------------------------------------
# 3. Money validation
# ----------------------------------------------------------

def _money(value):
    """
    Return a positive, exactly representable 2-decimal string.

    Never round a source amount just to satisfy the agent contract.
    """

    try:
        amount = Decimal(str(value))

        if (
            not amount.is_finite()
            or amount <= 0
            or amount != amount.quantize(Decimal("0.01"))
        ):
            raise ValueError(
                "Amount is not representable as "
                f"positive 2-decimal money: {value}"
            )

        return format(amount, ".2f")

    except (InvalidOperation, TypeError) as exc:
        raise ValueError(
            f"Invalid transaction amount: {value}"
        ) from exc


# ----------------------------------------------------------
# 4. Timestamp validation and timezone conversion
# ----------------------------------------------------------

def _time(value, source_timezone):
    """
    Convert source timestamp to timezone-aware ISO format.

    Naive timestamps are interpreted in the explicitly supplied
    source timezone.
    """

    if value is None:
        raise ValueError("Transaction timestamp is missing")

    # PostgreSQL returns datetime objects; strings are still accepted.
    dt = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=source_timezone)

    return dt.isoformat()


# ----------------------------------------------------------
# 5. TeamBackend adapter
# ----------------------------------------------------------

class TeamBackend:
    """
    Read-only Member 1 backend adapter.

    Source database: Member 1 PostgreSQL (DATABASE_URL, or a dedicated
    read-only login via AML_SOURCE_DATABASE_URL).
    Agent persistence database: separate agent_runtime.db (SQLite).

    Only returns validated AlertBundle objects.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        source_timezone: str,
        window_hours: int = 48,
        max_transactions: int = 200,
        timeout_seconds: float = 3,
    ):

        url = (
            database_url
            or os.getenv("AML_SOURCE_DATABASE_URL")
            or os.getenv("DATABASE_URL")
        )

        if not url:
            raise ValueError(
                "Member 1 database URL is required "
                "(argument, AML_SOURCE_DATABASE_URL or DATABASE_URL)"
            )

        # Explicit timezone avoids silently guessing IBM timestamps.
        self.source_timezone = (
            timezone.utc
            if source_timezone == "UTC"
            else ZoneInfo(source_timezone)
        )

        if (
            window_hours < 1
            or max_transactions < 2
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "Invalid history-window, row-limit or timeout"
            )

        self.window = timedelta(hours=window_hours)
        self.limit = max_transactions
        self.timeout = timeout_seconds

        # Small dedicated pool; every use is a READ ONLY transaction.
        self.engine = create_engine(
            normalize_database_url(url),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=2,
            pool_recycle=1800,
            connect_args={
                "connect_timeout": max(1, int(timeout_seconds)),
                "application_name": "amlens-agent-adapter",
                # timestamptz values come back as UTC, exactly as before.
                "options": "-c timezone=UTC",
            },
        )

    def close(self):
        """Release pooled database connections."""
        self.engine.dispose()

    @contextmanager
    def _read_only(self):
        """
        Yield a connection inside a READ ONLY transaction.

        PostgreSQL rejects any INSERT/UPDATE/DELETE/DDL in it, and every
        statement is bounded by the configured timeout (the equivalent of
        the former SQLite query_only + busy_timeout pragmas).
        """
        timeout_ms = str(int(self.timeout * 1000))

        with self.engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(
                    text(
                        "SELECT set_config('statement_timeout', :ms, true), "
                        "set_config('lock_timeout', :ms, true)"
                    ),
                    {"ms": timeout_ms},
                )
                yield conn

    # ------------------------------------------------------
    # 6. Main interface required by LangGraph agents
    # ------------------------------------------------------

    def get_alert_context(self, alert_id: str) -> AlertBundle:
        """
        Return a validated AlertBundle for a stored alert.

        A source read occurs only after consuming the backend.read
        budget. There are no automatic retries in this method.
        """

        if not alert_id:
            raise ValueError("alert_id is required")

        # Required agent audit-budget call.
        # Must occur BEFORE the database read attempt.
        consume("backend.read")

        with self._read_only() as conn:

            # --------------------------------------------------
            # 7. Retrieve the requested alert
            # --------------------------------------------------

            alert = conn.execute(
                text(
                    """
                    SELECT
                        id,
                        transaction_id,
                        rule_id,
                        description,
                        evidence,
                        status,
                        created_at
                    FROM alerts
                    WHERE id = :alert_id
                    """
                ),
                {"alert_id": alert_id},
            ).mappings().fetchone()

            if alert is None:
                raise KeyError(
                    f"Alert not found: {alert_id}"
                )

            if not alert["created_at"]:
                raise ValueError(
                    "Alert created_at is missing; "
                    "create a new alert with a real timestamp"
                )

            if alert["rule_id"] not in RULE_TO_TYPOLOGY:
                raise ValueError(
                    f"Unsupported rule ID: {alert['rule_id']}"
                )

            # --------------------------------------------------
            # 8. Parse alert evidence
            # --------------------------------------------------

            evidence = (
                json.loads(alert["evidence"])
                if isinstance(alert["evidence"], str)
                else alert["evidence"]
            )

            if not isinstance(evidence, dict):
                raise ValueError(
                    "Alert evidence must be a JSON object"
                )

            # --------------------------------------------------
            # 9. Retrieve triggering transaction
            # --------------------------------------------------

            trigger = conn.execute(
                text(
                    """
                    SELECT *
                    FROM transactions
                    WHERE id = :transaction_id
                    """
                ),
                {"transaction_id": alert["transaction_id"]},
            ).mappings().fetchone()

            if trigger is None:
                raise RuntimeError(
                    "Triggering transaction missing"
                )

            dataset_id = trigger["dataset_id"]

            if not dataset_id:
                raise ValueError(
                    "Triggering transaction has no dataset_id"
                )

            # --------------------------------------------------
            # 10. Determine investigated account
            # --------------------------------------------------

            anchor = (
                evidence.get("anchor_account_token")
                or evidence.get("account_token")
            )

            if not anchor:
                raise ValueError(
                    "Alert lacks explicit anchor_account_token"
                )

            if anchor not in (
                trigger["sender_token"],
                trigger["receiver_token"],
            ):
                raise ValueError(
                    "Anchor account does not belong to "
                    "the triggering transaction"
                )

            # --------------------------------------------------
            # 11. Define the bounded history window
            # --------------------------------------------------

            # transactions.timestamp is timezone-naive (source zone),
            # so the window bounds are naive datetimes too.
            trigger_dt = trigger["timestamp"]

            if not isinstance(trigger_dt, datetime):
                trigger_dt = datetime.fromisoformat(
                    str(trigger_dt).replace("Z", "+00:00")
                )

            if trigger_dt.tzinfo is not None:
                trigger_dt = (
                    trigger_dt
                    .astimezone(self.source_timezone)
                    .replace(tzinfo=None)
                )

            start = trigger_dt - self.window

            end = trigger_dt + self.window

            # --------------------------------------------------
            # 12. Retrieve bounded account history
            #     (closest in time to the trigger first)
            # --------------------------------------------------

            rows = conn.execute(
                text(
                    """
                    SELECT t.*
                    FROM transactions AS t
                    WHERE t.dataset_id = :dataset_id
                      AND (
                        t.sender_token = :anchor
                        OR t.receiver_token = :anchor
                      )
                      AND t."timestamp" >= :start
                      AND t."timestamp" <= :end
                      AND t.id <> :trigger_id
                    ORDER BY
                        ABS(EXTRACT(EPOCH FROM (t."timestamp" - :trigger_ts))),
                        t.id
                    LIMIT :row_limit
                    """
                ),
                {
                    "dataset_id": dataset_id,
                    "anchor": anchor,
                    "start": start,
                    "end": end,
                    "trigger_id": alert["transaction_id"],
                    "trigger_ts": trigger_dt,
                    "row_limit": self.limit - 1,
                },
            ).mappings().fetchall()

        # Database connection is returned to the pool from here onward.

        # Always include the triggering transaction.
        selected = [trigger, *rows]

        if len({row["id"] for row in selected}) != len(selected):
            raise RuntimeError(
                "Duplicate transaction IDs"
            )

        # ------------------------------------------------------
        # 13. Identify evidence that must not be excluded
        # ------------------------------------------------------

        evidence_ids = evidence.get("transaction_ids", [])

        if not isinstance(evidence_ids, list):
            raise ValueError(
                "evidence.transaction_ids must be a list"
            )

        if not all(
            isinstance(transaction_id, str)
            and transaction_id
            for transaction_id in evidence_ids
        ):
            raise ValueError(
                "Invalid transaction ID in alert evidence"
            )

        required_ids = set(evidence_ids)

        # The alert trigger is always required.
        required_ids.add(alert["transaction_id"])

        # ------------------------------------------------------
        # 14. Convert database rows into agent transactions
        # ------------------------------------------------------

        mapped = []

        excluded_self_transfers = []

        for row in selected:

            incoming = (
                row["receiver_token"] == anchor
            )

            outgoing = (
                row["sender_token"] == anchor
            )

            if not (incoming or outgoing):
                raise ValueError(
                    "Unrelated transaction in account history: "
                    f"{row['id']}"
                )

            # --------------------------------------------------
            # 15. Safely handle self-transfers
            # --------------------------------------------------

            if incoming and outgoing:

                # Never remove evidence that caused the alert.
                if row["id"] in required_ids:
                    raise ValueError(
                        "Required alert evidence is a self-transfer: "
                        f"{row['id']}. "
                        "Cannot represent this transaction under "
                        "the current agent contract."
                    )

                # MVP compatibility policy:
                # Non-required self-transfers are excluded.
                # They remain unchanged in the source database.
                excluded_self_transfers.append(row["id"])

                continue

            # --------------------------------------------------
            # 16. Convert transaction direction
            # --------------------------------------------------

            if incoming:
                transaction_type = "deposit"

                counterparty_token = (
                    row["sender_token"]
                )

                currency_text = (
                    row["receiving_currency"]
                )

                amount_value = (
                    row["amount_received"]
                )

            else:
                transaction_type = "withdrawal"

                counterparty_token = (
                    row["receiver_token"]
                )

                currency_text = (
                    row["payment_currency"]
                )

                amount_value = (
                    row["amount_paid"]
                )

            # --------------------------------------------------
            # 17. Convert currency
            # --------------------------------------------------

            currency = CURRENCIES.get(currency_text)

            if not currency:
                raise ValueError(
                    "Unsupported currency mapping "
                    f"for {row['id']}: {currency_text}"
                )

            # --------------------------------------------------
            # 18. Build agent-compatible transaction
            # --------------------------------------------------

            mapped.append({
                "transaction_id": row["id"],
                "account_token": anchor,
                "counterparty_token": counterparty_token,
                "amount": _money(amount_value),
                "currency": currency,
                "timestamp": _time(
                    row["timestamp"],
                    self.source_timezone,
                ),
                "transaction_type": transaction_type,
                "description": (
                    "Incoming transaction"
                    if incoming
                    else "Outgoing transaction"
                ),
            })

        # ------------------------------------------------------
        # 19. Record omitted self-transfers in operational logs
        # ------------------------------------------------------

        if excluded_self_transfers:

            logger.warning(
                "INCOMPLETE AGENT HISTORY: "
                "Alert %s excluded %d non-required "
                "self-transfer transaction(s): %s. "
                "The resulting account history is incomplete.",
                alert_id,
                len(excluded_self_transfers),
                excluded_self_transfers,
            )

        # ------------------------------------------------------
        # 20. Verify all required evidence was included
        # ------------------------------------------------------

        mapped_ids = {
            transaction["transaction_id"]
            for transaction in mapped
        }

        missing_required = (
            required_ids - mapped_ids
        )

        if missing_required:
            raise ValueError(
                "Required alert evidence is missing from "
                "the bounded agent history: "
                f"{sorted(missing_required)}. "
                "Review the history window and transaction limit."
            )

        if not mapped:
            raise RuntimeError(
                "No valid transactions available "
                "for the selected alert"
            )

        # ------------------------------------------------------
        # 21. Sort transactions chronologically
        # ------------------------------------------------------

        mapped.sort(
            key=lambda transaction: (
                transaction["timestamp"],
                transaction["transaction_id"],
            )
        )

        # ------------------------------------------------------
        # 22. Construct and validate AlertBundle
        # ------------------------------------------------------

        bundle = AlertBundle.model_validate({
            "alert": {
                "alert_id": alert["id"],
                "transaction_id": alert["transaction_id"],
                "label": (
                    alert["rule_id"]
                    .replace("_", " ")
                    .title()
                    + " review alert"
                ),
                "typology": RULE_TO_TYPOLOGY[
                    alert["rule_id"]
                ],
                "status": alert["status"].lower(),
                "created_at": _time(
                    alert["created_at"],
                    timezone.utc,
                ),
                # No verified case information was supplied.
                "information_status": {},
            },
            "transactions": mapped,
        })

        logger.info(
            "AlertBundle created for %s: "
            "%d transactions; %d excluded self-transfers",
            alert_id,
            len(mapped),
            len(excluded_self_transfers),
        )

        return bundle

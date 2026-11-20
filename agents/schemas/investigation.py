from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")

class Transaction(StrictModel):
    transaction_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    account_token: str
    counterparty_token: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timestamp: datetime
    transaction_type: Literal["deposit", "withdrawal"]
    description: str = ""

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, v):
        if v.tzinfo is None:
            raise ValueError("Timezone-aware timestamps required")
        return v

GapStatus = Literal["confirmed_missing", "not_provided", "not_applicable", "available_verified"]

class AlertContext(StrictModel):
    alert_id: str
    transaction_id: str
    label: str
    typology: Literal["structuring", "rapid_movement", "fan_in_out", "unusual_activity"]
    status: str
    created_at: str
    # These statuses are supplied by the backend, never inferred from absent text.
    information_status: dict[str, GapStatus] = Field(default_factory=dict)

class AlertBundle(StrictModel):
    alert: AlertContext
    transactions: list[Transaction]

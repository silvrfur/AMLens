from pydantic import Field
from .investigation import StrictModel

class InvestigationMessage(StrictModel):
    alert_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    investigation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")

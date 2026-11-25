from typing import Literal
from pydantic import BaseModel, Field

class DecisionIn(BaseModel):
    decision: Literal['APPROVE','REJECT','ESCALATE']
    rationale: str = Field(min_length=10, max_length=5000)
    analyst_id: str = Field(min_length=1, max_length=100)

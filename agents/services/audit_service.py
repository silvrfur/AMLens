import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import uuid4
from .security import ALLOWED_TOOLS
from .timeutil import utcnow

log = logging.getLogger("traceiq")
current_budget: ContextVar = ContextVar("budget", default=None)

class ToolBudgetExceeded(RuntimeError):
    pass

@dataclass
class ToolBudget:
    db: object
    investigation_id: str
    limit: int = 8
    calls: int = 0
    run_id: str | None = None

    def consume(self, tool_name: str):
        if tool_name not in ALLOWED_TOOLS:
            raise PermissionError("Tool is not allowed")
        if self.calls >= self.limit:
            raise ToolBudgetExceeded("External tool call budget exhausted")
        self.calls += 1
        if self.run_id:
            with self.db.connect() as c:
                c.execute("INSERT INTO tool_calls (call_id,run_id,tool_name,input_json,output_json,created_at) VALUES (?,?,?,?,?,?)",
                          (str(uuid4()), self.run_id, tool_name, '{}', '{"status":"attempted"}', utcnow()))
        log.info(json.dumps({"event": "tool_attempt", "tool": tool_name,
                             "investigation_id": self.investigation_id, "count": self.calls}))

def consume(tool_name):
    budget = current_budget.get()
    if budget:
        budget.consume(tool_name)

def audit(db, investigation_id, event_type, details):
    with db.connect() as c:
        c.execute("INSERT INTO audit_log (event_id,investigation_id,event_type,actor,timestamp,details_json) VALUES (?,?,?,?,?,?)",
                  (str(uuid4()), investigation_id, event_type, "agent_workflow", utcnow(), json.dumps(details)))
    log.info(json.dumps({"event": event_type, "investigation_id": investigation_id, **details}))

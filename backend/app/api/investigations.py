"""Review-side case API. Agent execution and report persistence are separate.

Local MVP: synchronous, mocked-agent execution only. Never expose publicly without
identification, RBAC, rate limits, worker/queue integration and an audit review.
"""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.tables import Alert, Investigation, InvestigatorDecision, AuditEvent
from app.models.schemas import DecisionIn
from app.services import agent_bridge

router = APIRouter()

# Alert statuses, as the frontend's alert queue filters and badges expect them.
ALERT_OPEN = 'OPEN'
ALERT_UNDER_REVIEW = 'UNDER REVIEW'
ALERT_DECIDED = 'DECIDED'


def _agent_record(investigation_id: str, persistence=None):
    try:
        return (persistence or agent_bridge.get_agent_persistence()).get(investigation_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Agent persistence unavailable') from exc


_NO_VERIFICATION = {'passed': False, 'errors': [], 'warnings': []}
# Case status -> run status when the agents have not persisted a record yet.
_PENDING_EXECUTION = {'RUNNING': 'running', 'FAILED': 'failed'}


def _decision_out(d):
    if d is None:
        return None
    return {'decision_id': d.id, 'decision': d.decision, 'rationale': d.rationale,
            'analyst_id': d.analyst_id, 'created_at': d.created_at.isoformat()}


def _summary(inv, record, decision):
    """Case summary shared by the list and detail endpoints (always the same shape)."""
    return {'investigation_id': inv.id, 'alert_id': inv.alert_id, 'status': inv.status,
            'execution_status': record['execution_status'] if record
            else _PENDING_EXECUTION.get(inv.status, 'pending'),
            'report_available': record is not None and record['report'] is not None,
            'verification': (record and record['verification']) or dict(_NO_VERIFICATION),
            'created_at': inv.created_at.isoformat(),
            'decision': _decision_out(decision)}


@router.get('/investigations')
def list_investigations(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Newest cases first, with each run's status and verification."""
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(400, 'Invalid pagination')
    cases = (db.query(Investigation).order_by(Investigation.created_at.desc(), Investigation.id)
             .offset(offset).limit(limit).all())
    decisions = {d.investigation_id: d for d in db.query(InvestigatorDecision)
                 .filter(InvestigatorDecision.investigation_id.in_([c.id for c in cases]))}
    try:
        persistence = agent_bridge.get_agent_persistence()
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Agent persistence unavailable') from exc
    return [_summary(c, _agent_record(c.id, persistence), decisions.get(c.id)) for c in cases]


@router.post('/investigate/{alert_id}', status_code=201)
def start_investigation(alert_id: str, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, 'Alert not found')
    # Alert lifecycle: OPEN -> UNDER REVIEW (investigation opened) -> DECIDED (human decision).
    # Only moves forward: a new investigation never reopens a decided alert.
    if alert.status == ALERT_OPEN:
        alert.status = ALERT_UNDER_REVIEW
    inv = Investigation(id=str(uuid4()), alert_id=alert_id, status='PENDING_AGENT')
    db.add(inv)
    # Insert the parent row first: PostgreSQL enforces the audit_history ->
    # investigations foreign key (SQLite silently did not).
    db.flush()
    db.add(AuditEvent(id=str(uuid4()), investigation_id=inv.id, action='CREATED',
                      details={'alert_id': alert_id}))
    db.commit()
    return {'investigation_id': inv.id, 'alert_id': alert_id, 'status': inv.status}


@router.post('/investigations/{id}/run')
def run_investigation(id: str, db: Session = Depends(get_db)):
    """Run the agent workflow synchronously (LLM/RAG mock or live per USE_MOCK_LLM / USE_MOCK_RAG)."""
    inv = db.get(Investigation, id)
    if not inv:
        raise HTTPException(404, 'Investigation not found')
    existing = _agent_record(id)
    if existing and existing['alert_id'] != inv.alert_id:
        raise HTTPException(409, 'Investigation ID belongs to a different alert')
    if existing and existing['execution_status'] in ('completed', 'incomplete'):
        return {'investigation_id': id, 'alert_id': inv.alert_id,
                'execution_status': existing['execution_status'], 'report_available': existing['report'] is not None}
    if inv.status not in ('PENDING_AGENT', 'FAILED'):
        raise HTTPException(409, 'Investigation is not available to run')

    # Import here so report-only endpoints do not initialize the LangGraph runner.
    from agents.schemas.messages import InvestigationMessage
    from agents.services.persistence import InvestigationBusy, InvestigationConflict
    from agents.graph import InvestigationFailed

    inv.status = 'RUNNING'
    db.add(AuditEvent(id=str(uuid4()), investigation_id=id, action='AGENT_RUN_REQUESTED', details={}))
    db.commit()
    try:
        services = agent_bridge.get_agent_services()
        try:
            result = services.runner.run(InvestigationMessage(alert_id=inv.alert_id, investigation_id=id))
        finally:
            services.close()
    except (InvestigationBusy, InvestigationConflict) as exc:
        inv.status = 'PENDING_AGENT'
        db.commit()
        raise HTTPException(409, str(exc)) from None
    except Exception:
        inv.status = 'FAILED'
        db.add(AuditEvent(id=str(uuid4()), investigation_id=id, action='AGENT_RUN_FAILED', details={}))
        db.commit()
        raise HTTPException(503, 'Agent investigation failed; inspect persisted status') from None

    inv.status = result['execution_status'].upper()
    db.add(AuditEvent(id=str(uuid4()), investigation_id=id, action='AGENT_RUN_FINISHED',
                      details={'execution_status': result['execution_status']}))
    db.commit()
    return {'investigation_id': id, 'alert_id': inv.alert_id,
            'execution_status': result['execution_status'], 'report_available': result['report'] is not None}


@router.get('/investigations/{id}')
def get_investigation(id: str, db: Session = Depends(get_db)):
    inv = db.get(Investigation, id)
    if not inv:
        raise HTTPException(404, 'Investigation not found')
    a = db.get(Alert, inv.alert_id)
    decision = db.query(InvestigatorDecision).filter_by(investigation_id=id).first()
    return {**_summary(inv, _agent_record(id), decision),
            'evidence': a.evidence, 'rule_id': a.rule_id}


@router.get('/investigations/{id}/report')
def get_report(id: str, db: Session = Depends(get_db)):
    if not db.get(Investigation, id):
        raise HTTPException(404, 'Investigation not found')
    record = _agent_record(id)
    if not record or record['report'] is None:
        raise HTTPException(404, 'Report not available')
    return {'investigation_id': id, 'execution_status': record['execution_status'],
            'label': 'AI-Generated Draft — Requires Investigator Review',
            'report': record['report'], 'verification': record['verification'],
            'agent_execution_trace': record['agent_execution_trace']}


@router.post('/investigations/{id}/decision')
def decide(id: str, payload: DecisionIn, request: Request, db: Session = Depends(get_db)):
    # Behind the authenticated proxy, record who is actually signed in, not what the browser sent.
    analyst_id = getattr(request.state, 'user', None) or payload.analyst_id
    inv = db.get(Investigation, id)
    if not inv:
        raise HTTPException(404, 'Investigation not found')
    record = _agent_record(id)
    if not record or record['execution_status'] not in ('completed', 'incomplete'):
        raise HTTPException(409, 'Investigation report must be generated before a review decision')
    if payload.decision == 'APPROVE' and (record['execution_status'] != 'completed' or not (record['verification'] or {}).get('passed')):
        raise HTTPException(409, 'Cannot approve an incomplete or unverified AI report')
    if db.query(InvestigatorDecision).filter_by(investigation_id=id).first():
        raise HTTPException(409, 'A decision has already been recorded for this investigation')
    d = InvestigatorDecision(id=str(uuid4()), investigation_id=id,
                             decision=payload.decision, rationale=payload.rationale,
                             analyst_id=analyst_id)
    inv.status = payload.decision
    alert = db.get(Alert, inv.alert_id)
    if alert:
        alert.status = ALERT_DECIDED
    db.add(d)
    db.add(AuditEvent(id=str(uuid4()), investigation_id=id, action='DECISION_RECORDED',
                      details={'decision': payload.decision, 'analyst_id': analyst_id,
                               'decision_id': d.id, 'rationale': payload.rationale}))
    db.commit()
    return {**_decision_out(d), 'investigation_id': id, 'status': inv.status}


@router.get('/audit/{id}')
def audit(id: str, db: Session = Depends(get_db)):
    if not db.get(Investigation, id):
        raise HTTPException(404, 'Investigation not found')
    events = db.query(AuditEvent).filter_by(investigation_id=id).order_by(AuditEvent.created_at, AuditEvent.id).all()
    return [{'event_id': e.id, 'action': e.action, 'details': e.details,
             'created_at': e.created_at.isoformat()} for e in events]

"""Review-side case API. Agent execution and report persistence are separate.

Local MVP: synchronous, mocked-agent execution only. Never expose publicly without
identification, RBAC, rate limits, worker/queue integration and an audit review.
"""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.tables import Alert, Investigation, InvestigatorDecision, AuditEvent
from app.models.schemas import DecisionIn
from app.services import agent_bridge

router = APIRouter()


def _agent_record(investigation_id: str):
    try:
        return agent_bridge.get_agent_persistence().get(investigation_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Agent persistence unavailable') from exc


@router.post('/investigate/{alert_id}', status_code=201)
def start_investigation(alert_id: str, db: Session = Depends(get_db)):
    if not db.get(Alert, alert_id):
        raise HTTPException(404, 'Alert not found')
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
    """DEV ONLY: run the agent workflow synchronously using mock LLM and mock RAG."""
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
    result = _agent_record(id)
    return {'investigation_id': id, 'alert_id': inv.alert_id,
            'status': inv.status,
            'execution_status': result['execution_status'] if result else None,
            'report_available': result is not None and result['report'] is not None,
            'verification': result['verification'] if result else None,
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
def decide(id: str, payload: DecisionIn, db: Session = Depends(get_db)):
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
                             analyst_id=payload.analyst_id)
    inv.status = payload.decision
    db.add(d)
    db.add(AuditEvent(id=str(uuid4()), investigation_id=id, action='DECISION_RECORDED',
                      details={'decision': payload.decision, 'analyst_id': payload.analyst_id,
                               'decision_id': d.id, 'rationale': payload.rationale}))
    db.commit()
    return {'decision_id': d.id, 'investigation_id': id, 'status': inv.status}


@router.get('/audit/{id}')
def audit(id: str, db: Session = Depends(get_db)):
    if not db.get(Investigation, id):
        raise HTTPException(404, 'Investigation not found')
    events = db.query(AuditEvent).filter_by(investigation_id=id).order_by(AuditEvent.created_at, AuditEvent.id).all()
    return [{'event_id': e.id, 'action': e.action, 'details': e.details,
             'created_at': e.created_at.isoformat()} for e in events]

from fastapi import APIRouter, Request, HTTPException
from ..schemas.messages import InvestigationMessage
from ..services.persistence import InvestigationBusy, InvestigationConflict
from ..graph import InvestigationFailed
router = APIRouter()

@router.get('/health')
def health(request: Request):
    with request.app.state.services.persistence.db.connect() as c:
        c.execute('SELECT 1').fetchone()
    return {'status': 'ok', 'human_review_required': True}

@router.post('/investigations/run')
def run(message: InvestigationMessage, request: Request):
    try: return request.app.state.services.runner.run(message)
    except (InvestigationBusy, InvestigationConflict) as exc:
        raise HTTPException(409, str(exc)) from None
    except InvestigationFailed:
        raise HTTPException(503, 'Investigation failed; inspect persisted status') from None

@router.post('/investigations/queue', status_code=202)
def queue(message: InvestigationMessage, request: Request):
    services = request.app.state.services
    existing = services.persistence.get(message.investigation_id)
    if existing and existing['alert_id'] != message.alert_id:
        raise HTTPException(409, 'Investigation ID already belongs to another alert')
    try: services.bus.send(message)
    except Exception: raise HTTPException(503, 'Queue unavailable') from None
    return {'investigation_id': message.investigation_id, 'status': 'queued'}

@router.get('/investigations/{investigation_id}')
def get(investigation_id: str, request: Request):
    result = request.app.state.services.persistence.get(investigation_id)
    if result is None: raise HTTPException(404, 'Investigation not found')
    return result

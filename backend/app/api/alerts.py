from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.tables import Alert
router = APIRouter()

def alert_out(a):
    return {'id': a.id, 'transaction_id': a.transaction_id, 'rule_id': a.rule_id,
            'description': a.description, 'evidence': a.evidence, 'status': a.status,
            'created_at': a.created_at.isoformat() if a.created_at else None}

@router.get('/alerts')
def list_alerts(limit: int=50, offset: int=0, db: Session=Depends(get_db)):
    """One page of alerts plus the total count, so clients can paginate."""
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(400, 'Invalid pagination')
    total = db.query(func.count(Alert.id)).scalar()
    items = [alert_out(a) for a in db.query(Alert).order_by(Alert.id).offset(offset).limit(limit)]
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset}

@router.get('/alerts/{alert_id}')
def get_alert(alert_id: str, db: Session=Depends(get_db)):
    a = db.get(Alert,alert_id)
    if not a:
        raise HTTPException(404, 'Alert not found')
    return alert_out(a)

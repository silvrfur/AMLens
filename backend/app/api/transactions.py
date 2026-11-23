from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.tables import Transaction
router = APIRouter()

@router.get('/accounts/{account_id}/history')
def account_history(account_id: str, limit: int=100, db: Session=Depends(get_db)):
    if limit < 1 or limit > 500:
        raise HTTPException(400, 'Limit must be 1–500')
    txs = (db.query(Transaction).filter(or_(Transaction.sender_token==account_id,
                                           Transaction.receiver_token==account_id))
           .order_by(Transaction.timestamp.desc(), Transaction.id).limit(limit).all())
    return [{'transaction_id': t.id, 'source_row':t.source_row,
             'timestamp': t.timestamp.isoformat(), 'sender_token':t.sender_token,
             'receiver_token':t.receiver_token, 'amount_paid':str(t.amount_paid),
             'payment_currency':t.payment_currency, 'amount_received':str(t.amount_received),
             'receiving_currency':t.receiving_currency, 'payment_format':t.payment_format}
            for t in txs]

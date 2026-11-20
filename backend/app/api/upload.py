from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.ingestion import ingest_csv, MAX_UPLOAD

router = APIRouter()
@router.post('/upload-transactions')
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(400, 'CSV file required')
    content = await file.read(MAX_UPLOAD+1)
    try:
        return ingest_csv(content, db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e)) from e

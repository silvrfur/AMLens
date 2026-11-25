import hashlib
import io
import os
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from app.database.tables import Transaction, Alert
from app.services.validation import validate_frame
from app.services.transaction_analysis import generate_findings
from app.utils.tokenization import account_token
from datetime import datetime, timezone

MAX_UPLOAD = 20 * 1024 * 1024  # local MVP only
MAX_ROWS = 100_000

def ingest_csv(content: bytes, db: Session):
    if len(content) > MAX_UPLOAD:
        raise ValueError('MVP upload limit is 20 MB. Split the full dataset first.')
    dataset_id = hashlib.sha256(content).hexdigest()[:20]
    if db.query(Transaction).filter_by(dataset_id=dataset_id).first():
        raise ValueError('Dataset already imported')
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:
        raise ValueError(f'Could not parse CSV: {e}') from e
    if len(df) > MAX_ROWS:
        raise ValueError(f'MVP limit is {MAX_ROWS:,} rows; use a representative subset.')
    df['_source_row'] = range(2, len(df)+2)  # 1-based file lines, including header
    accepted, rejected = validate_frame(df)
    transactions = []
    for r in accepted:
        source_row = int(r['_source_row'])
        tid = f'TX_{dataset_id}_{source_row}'
        transactions.append(Transaction(
            id=tid, dataset_id=dataset_id, source_row=source_row,
            timestamp=r['_timestamp'],
            sender_token=account_token(r['From Bank'],r['Account']),
            receiver_token=account_token(r['To Bank'],r['Account.1']),
            amount_paid=r['_amount_paid'], payment_currency=r['Payment Currency'],
            amount_received=r['_amount_received'], receiving_currency=r['Receiving Currency'],
            payment_format=r['Payment Format']))
    # Raw file and labels are deliberately not persisted by this demo. Configure
    # a restricted evaluation-only storage location before real benchmark runs.
    db.add_all(transactions)
    db.flush()
    findings = generate_findings(transactions)
    for i, f in enumerate(findings, 1):
        db.add(Alert(
            id=f'AL_{dataset_id}_{i}',
            transaction_id=f['transaction_id'],
            rule_id=f['rule_id'],
            description=f['description'],
            evidence=f['evidence'],
            created_at=datetime.now(timezone.utc)
        ))
    db.commit()
    return {'dataset_id': dataset_id, 'accepted': len(accepted), 'rejected': len(rejected),
            'rejection_reasons': rejected[:50], 'rejection_reasons_truncated': len(rejected)>50,
            'alerts_created': len(findings), 'ground_truth_exposed': False}

import json
from pathlib import Path

GUIDANCE = [
    {"chunk_id": "DEMO-STRUCT-001", "text": "Repeated deposits near an illustrative review threshold can justify examining the economic rationale. Such activity alone does not establish wrongdoing.", "source": "AMLens illustrative training material (not regulatory guidance)", "section": "Structuring indicators", "page": 1, "typology": "structuring", "relevance_score": 0.92},
    {"chunk_id": "DEMO-RAPID-001", "text": "Incoming funds followed shortly by outgoing transfers may merit review of transaction purpose and supporting documents.", "source": "AMLens illustrative training material (not regulatory guidance)", "section": "Rapid movement indicators", "page": 2, "typology": "rapid_movement", "relevance_score": 0.90},
    {"chunk_id": "DEMO-FAN-001", "text": "Multiple counterparties on incoming and outgoing payments can prompt questions about the underlying business relationships.", "source": "AMLens illustrative training material (not regulatory guidance)", "section": "Counterparty patterns", "page": 3, "typology": "fan_in_out", "relevance_score": 0.88},
]

def seed(db):
    transactions = [
        ('TX-001','synthetic-account-A','synthetic-CP-1','9800.00','USD','2026-01-10T09:00:00+00:00','deposit','Synthetic customer receipt'),
        ('TX-002','synthetic-account-A','synthetic-CP-2','9700.00','USD','2026-01-10T09:20:00+00:00','deposit','Synthetic invoice settlement'),
        ('TX-003','synthetic-account-A','synthetic-CP-3','9900.00','USD','2026-01-10T09:40:00+00:00','deposit','Synthetic business receipt'),
        ('TX-004','synthetic-account-A','synthetic-CP-4','18000.00','USD','2026-01-10T10:00:00+00:00','withdrawal','Synthetic supplier payment'),
        ('TX-005','synthetic-account-A','synthetic-CP-5','10000.00','USD','2026-01-10T10:10:00+00:00','withdrawal','Synthetic transfer'),
        ('TX-006','synthetic-account-B','synthetic-CP-6','124.35','EUR','2026-01-11T12:00:00+00:00','deposit','Synthetic refund'),
    ]
    with db.connect() as c:
        c.executemany('INSERT OR IGNORE INTO transactions VALUES (?,?,?,?,?,?,?,?)', transactions)
        c.executemany('INSERT OR IGNORE INTO alerts VALUES (?,?,?,?,?,?)', [
            ('ALT-001','TX-001','Synthetic review alert','structuring','open','2026-01-10T11:00:00Z'),
            ('ALT-002','TX-006','Synthetic baseline alert','unusual_activity','open','2026-01-11T13:00:00Z')])

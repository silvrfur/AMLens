# Validation record

Executed in the provided Linux workspace with Python 3.12.3. Dependencies installed from
requirements.txt; resolved versions captured in requirements-lock.txt. No real Groq or Azure
credentials were used. All pytest tests prohibit socket connections to external services.

## Results

```text
python -m pytest agents/tests -q
74 passed in 3.94s

pip check
No broken requirements found.
```

- Python compilation of all modules: passed.
- SQLite clean sample: integrity_check `ok`; 2 alerts, 6 transactions, 0 investigations.
- Real LangGraph normal sequence: transaction, retrieval, evidence, information_gap,
  report, verify; persisted `completed`, verification passed.
- Correction scenario: same sequence plus correction, reverify; persisted `completed`.
  Initial verification failure remains in the audit history.
- Always-invalid narrative: exactly one correction; persisted `incomplete`.
- Standalone mock worker: `['completed']`.
- Live Uvicorn startup on loopback: passed.
- Live HTTP GET /health: `200`, status `ok`.
- Live HTTP POST /investigations/run: `200`, `completed`, verification passed.
- Live HTTP GET /investigations/{id}: `200`.
- Live HTTP POST /investigations/queue: `202`.
- Optional local FAISS IndexFlatIP: exercised by pytest.
- Official Groq and Azure SDK request construction: exercised with stub transports.
- Real Groq inference, live Azure infrastructure and actual Member 1/2 services: not tested;
  configuration and external credentials/services are required.

The supplied sample database contains no generated investigation output. Demo runtime DBs,
virtual environments, Python/pytest caches and secrets are excluded by scripts/package_project.py.

## Extracted deliverable check

The ZIP was extracted into a fresh temporary directory. Running the full test suite there
produced `74 passed in 4.08s`. The complete offline demo also exited successfully there,
creating a new runtime database and exercising all three scenarios. Archive CRC validation
passed; the deliverable contains 69 files, including the clean synthetic database and
`.env.example`, with no environment, cache or runtime-database artifacts.

import json
import time
from uuid import uuid4
from .audit_service import audit

class InvestigationBusy(RuntimeError): pass
class InvestigationConflict(ValueError): pass
class LostLease(RuntimeError): pass

class Persistence:
    def __init__(self, db, lease_seconds=900):
        self.db, self.lease_seconds = db, lease_seconds

    def claim(self, message):
        owner = str(uuid4())
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM investigations WHERE investigation_id=?", (message.investigation_id,)).fetchone()
            if row:
                if row['alert_id'] != message.alert_id:
                    raise InvestigationConflict("Investigation ID already belongs to another alert")
                if row['execution_status'] in ('completed', 'incomplete'): return None
                if row['execution_status'] == 'running' and row['lease_until'] > time.time():
                    raise InvestigationBusy("Investigation already running")
                c.execute("UPDATE investigations SET execution_status='running', lease_owner=?,lease_until=?,updated_at=datetime('now') WHERE investigation_id=?",
                          (owner, time.time()+self.lease_seconds, message.investigation_id))
            else:
                c.execute("""INSERT INTO investigations VALUES (?,?,'running',NULL,NULL,datetime('now'),datetime('now'),?,?)""",
                          (message.investigation_id, message.alert_id, owner, time.time()+self.lease_seconds))
        return owner

    def save(self, state):
        report = state.get('final_report')
        verification = state.get('verification_result')
        status = state['execution_status']
        with self.db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            result = c.execute("""UPDATE investigations SET execution_status=?,report_json=?,verification_json=?,
                updated_at=datetime('now'),lease_until=0 WHERE investigation_id=? AND lease_owner=?""",
                (status, report.model_dump_json() if report else None,
                 verification.model_dump_json() if verification else None,
                 state['investigation_id'], state['lease_owner']))
            if result.rowcount != 1: raise LostLease("Stale investigation writer rejected")
            c.execute("INSERT INTO audit_log VALUES (?,?,?,'agent_workflow',datetime('now'),?)",
                (str(uuid4()), state['investigation_id'], 'persisted', json.dumps({
                    'status': status, 'errors': state.get('errors', []),
                    'trace': state.get('agent_execution_trace', [])})))

    def get(self, investigation_id):
        with self.db.connect() as c:
            row = c.execute("SELECT investigation_id,alert_id,execution_status,report_json,verification_json,created_at,updated_at FROM investigations WHERE investigation_id=?", (investigation_id,)).fetchone()
            if row is None: return None
            result = dict(row)
            result['report'] = json.loads(result.pop('report_json') or 'null')
            result['verification'] = json.loads(result.pop('verification_json') or 'null')
            result['agent_execution_trace'] = [dict(r) for r in c.execute(
                "SELECT agent_name,execution_status,error_message FROM agent_runs WHERE investigation_id=? ORDER BY rowid", (investigation_id,))]
            result['audit_history'] = [{**dict(r), 'details': json.loads(r['details_json'])} for r in c.execute(
                "SELECT event_type,timestamp,details_json FROM audit_log WHERE investigation_id=? ORDER BY rowid", (investigation_id,))]
        return result

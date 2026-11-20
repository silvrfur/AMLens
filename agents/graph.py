from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from langgraph.graph import StateGraph, START, END
from .state import InvestigationState
from .agents.transaction_agent import TransactionAgent
from .agents.aml_retrieval_agent import AMLRetrievalAgent
from .agents.evidence_agent import EvidenceAgent
from .agents.information_gap_agent import InformationGapAgent
from .agents.report_agent import ReportAgent
from .verifier.report_verifier import ReportVerifier
from .services.audit_service import ToolBudget, current_budget, audit

class InvestigationFailed(RuntimeError): pass

def build_graph(backend, rag, llm, persistence):
    db = persistence.db
    def traced(name, action):
        def node(state):
            run_id = str(uuid4())
            with db.connect() as c:
                c.execute("INSERT INTO agent_runs VALUES (?,?,?,'running',datetime('now'),NULL,NULL)",
                          (run_id, state['investigation_id'], name))
            budget = current_budget.get()
            if budget: budget.run_id = run_id
            error = None
            try:
                update = action(state)
            except ValidationError:
                error = 'StructuredOutputValidationError'
                if name in ('report', 'correction'):
                    update = {'final_report': None}
                else: update = {'execution_status': 'failed'}
            except Exception as exc:
                # Never persist arbitrary exception messages; provider errors may echo secrets/PII.
                error = type(exc).__name__
                update = {'execution_status': 'failed'}
            if name == 'correction': update['retry_count'] = 1
            status = 'failed' if error else 'completed'
            with db.connect() as c:
                c.execute("UPDATE agent_runs SET execution_status=?,completed_at=datetime('now'),error_message=? WHERE run_id=?",
                          (status, error, run_id))
            event = {'agent': name, 'status': status, 'error': error}
            update['agent_execution_trace'] = state.get('agent_execution_trace', []) + [event]
            if error: update['errors'] = state.get('errors', []) + [f'{name}: {error}']
            audit(db, state['investigation_id'], 'agent_execution', event)
            return update
        return node

    report = ReportAgent(llm)
    def correction(state):
        state = {**state, 'retry_count': 1}
        result = report(state)
        return {**result, 'retry_count': 1}
    def verify(state):
        result = ReportVerifier().verify(state)
        audit(db, state['investigation_id'], 'verification', result.model_dump())
        return {'verification_result': result,
                'errors': state.get('errors', []) + result.errors}
    def persist(state):
        status = state.get('execution_status')
        if status != 'failed':
            status = 'completed' if state['verification_result'].passed else 'incomplete'
        result = {**state, 'execution_status': status}
        persistence.save(result)
        return {'execution_status': status}

    builder = StateGraph(InvestigationState)
    nodes = {'transaction': TransactionAgent(backend), 'retrieval': AMLRetrievalAgent(rag),
             'evidence': EvidenceAgent(), 'information_gap': InformationGapAgent(),
             'report': report, 'verify': verify, 'correction': correction, 'reverify': verify}
    for name, action in nodes.items(): builder.add_node(name, traced(name, action))
    builder.add_node('persist', persist)
    builder.add_edge(START, 'transaction')
    sequence = ['transaction','retrieval','evidence','information_gap','report','verify']
    for source, target in zip(sequence, sequence[1:]):
        builder.add_conditional_edges(source, lambda s, t=target: 'persist' if s.get('execution_status') == 'failed' else t, ['persist', target])
    builder.add_conditional_edges('verify', lambda s: 'persist' if s.get('execution_status') == 'failed' or s['verification_result'].passed else 'correction', ['persist','correction'])
    builder.add_conditional_edges('correction', lambda s: 'persist' if s.get('execution_status') == 'failed' else 'reverify', ['persist','reverify'])
    builder.add_edge('reverify','persist')
    builder.add_edge('persist',END)
    return builder.compile()

class InvestigationRunner:
    def __init__(self, backend, rag, llm, persistence):
        self.persistence = persistence
        self.graph = build_graph(backend, rag, llm, persistence)

    def run(self, message):
        owner = self.persistence.claim(message)
        if owner is None: return self.persistence.get(message.investigation_id)
        initial = {'investigation_id': message.investigation_id, 'alert_id': message.alert_id,
                   'execution_status': 'running', 'retry_count': 0, 'errors': [],
                   'agent_execution_trace': [], 'lease_owner': owner}
        token = current_budget.set(ToolBudget(self.persistence.db, message.investigation_id))
        try:
            try:
                state = self.graph.invoke(initial, {'recursion_limit': 16})
            except Exception:
                # Best effort failure persistence; a DB outage still propagates and is never acknowledged.
                self.persistence.save({**initial, 'execution_status': 'failed', 'errors': ['WorkflowExecutionError']})
                raise InvestigationFailed('Workflow could not finish') from None
            if state['execution_status'] == 'failed': raise InvestigationFailed('Agent execution failed')
            return self.persistence.get(message.investigation_id)
        finally:
            current_budget.reset(token)

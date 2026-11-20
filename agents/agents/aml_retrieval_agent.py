from ..schemas.agent_outputs import RetrievalResult
from ..services.audit_service import consume

class AMLRetrievalAgent:
    def __init__(self, rag): self.rag = rag
    def __call__(self, state):
        typology = state['alert_context'].typology
        patterns = ', '.join(p.pattern_id for p in state['transaction_analysis'].observed_patterns)
        queries = [f'AML {typology} guidance for observed patterns: {patterns}',
                   f'{typology} indicators, evidence limitations and economic rationale review']
        best = RetrievalResult()
        notes = []
        for query in queries:
            consume('rag.search')
            result = RetrievalResult.model_validate(self.rag.search_aml_guidance(query, typology, 5))
            chunks = [g for g in result.retrieved_guidelines if g.typology == typology]
            if len({g.chunk_id for g in chunks}) != len(chunks): raise ValueError('Duplicate retrieved chunk IDs')
            notes.extend(result.relevance_notes)
            if max((g.relevance_score for g in chunks), default=-1) > max((g.relevance_score for g in best.retrieved_guidelines), default=-1):
                best = result.model_copy(update={'retrieved_guidelines': chunks})
            if any(g.relevance_score >= .65 for g in chunks): break
        if not best.retrieved_guidelines: notes.append('No matching guidance retrieved; no citations can be inferred.')
        return {'retrieved_guidelines': best.retrieved_guidelines,
                'source_references': best.source_references, 'relevance_notes': notes}

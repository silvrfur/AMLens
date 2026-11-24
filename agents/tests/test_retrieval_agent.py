import httpx
from agents.agents.aml_retrieval_agent import AMLRetrievalAgent
from agents.schemas.agent_outputs import RetrievalResult
from agents.services.rag_client import HTTPRAGClient
from agents.mocks.mock_rag import MockRAGClient
from agents.mocks.local_faiss import LocalFAISSDemoClient

class EmptyRAG:
    def __init__(self): self.queries=[]
    def search_aml_guidance(self, query, typology, top_k):
        self.queries.append(query)
        return RetrievalResult()

def test_metadata_and_filter(state):
    rag = MockRAGClient()
    result = AMLRetrievalAgent(rag)(state)
    chunk = result['retrieved_guidelines'][0]
    assert chunk.chunk_id == 'DEMO-STRUCT-001'
    assert chunk.page == 1 and chunk.relevance_score == .92
    assert len(rag.queries) == 1

def test_empty_reformulates_twice(state):
    rag = EmptyRAG()
    result = AMLRetrievalAgent(rag)(state)
    assert result['retrieved_guidelines'] == []
    assert len(rag.queries) == 2 and rag.queries[0] != rag.queries[1]

def test_queries_describe_typology_in_words(state):
    from agents.agents.aml_retrieval_agent import TYPOLOGY_DESCRIPTIONS
    rag = EmptyRAG()
    AMLRetrievalAgent(rag)(state)
    patterns = state['transaction_analysis'].observed_patterns
    for query in rag.queries:
        assert TYPOLOGY_DESCRIPTIONS[state['alert_context'].typology] in query
        assert all(p.pattern_id not in query for p in patterns)   # no raw IDs like "USD.round"
    assert all(p.description in rag.queries[0] for p in patterns)
    assert set(TYPOLOGY_DESCRIPTIONS) == {'structuring', 'rapid_movement', 'fan_in_out', 'unusual_activity'}

def test_weak_result_kept(state):
    class Weak(MockRAGClient):
        def search_aml_guidance(self,*args):
            result = super().search_aml_guidance(*args)
            result.retrieved_guidelines[0].relevance_score=.2
            return result
    rag=Weak()
    result=AMLRetrievalAgent(rag)(state)
    assert len(rag.queries)==2
    assert result['retrieved_guidelines'][0].relevance_score==.2

def test_http_contract():
    def handle(request):
        assert request.url.path == '/search'
        assert b'structuring' in request.content
        return httpx.Response(200,json=MockRAGClient().search_aml_guidance('x','structuring').model_dump())
    client=HTTPRAGClient('https://rag.example',httpx.Client(transport=httpx.MockTransport(handle)))
    assert client.search_aml_guidance('threshold','structuring').retrieved_guidelines[0].chunk_id=='DEMO-STRUCT-001'
    client.close()

def test_local_real_faiss():
    client=LocalFAISSDemoClient()
    result=client.search_aml_guidance('deposits threshold','structuring')
    assert result.retrieved_guidelines[0].relevance_score > 0
    assert not client.search_aml_guidance('x','unknown').retrieved_guidelines

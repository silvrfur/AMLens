from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from pydantic import ValidationError
from groq import RateLimitError, APITimeoutError, APIStatusError
from agents.services.groq_llm import GroqLLM, LLMUnavailable
from agents.agents.report_agent import NarrativeDraft

def response(content): return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

def service(effects):
    client=Mock()
    client.chat.completions.create.side_effect=effects
    return GroqLLM('test-key','test-model',client=client,sleep=lambda _:None),client

VALID='{"statements":["Review required."],"recommended_next_steps":["Review evidence."]}'

def test_valid_json_and_sdk_arguments():
    llm,client=service([response(VALID)])
    assert llm.generate_structured_response('system',{},NarrativeDraft).statements==['Review required.']
    args=client.chat.completions.create.call_args.kwargs
    assert args['model']=='test-model'
    assert args['response_format']=={'type':'json_object'}
    assert 'test-key' not in str(args)

@pytest.mark.parametrize('body',['not json','{}','{"statements":[]}'])
def test_invalid_json_schema(body):
    llm,_=service([response(body)])
    with pytest.raises(ValidationError): llm.generate_structured_response('system',{},NarrativeDraft)

def test_rate_limit_retry():
    error=RateLimitError('rate',response=httpx.Response(429,request=httpx.Request('POST','https://example.com')),body=None)
    llm,client=service([error,response(VALID)])
    llm.generate_structured_response('system',{},NarrativeDraft)
    assert client.chat.completions.create.call_count==2

def test_timeout_bounded():
    error=APITimeoutError(request=httpx.Request('POST','https://example.com'))
    llm,client=service([error,error,error])
    with pytest.raises(LLMUnavailable): llm.generate_structured_response('system',{},NarrativeDraft)
    assert client.chat.completions.create.call_count==3

def test_nontransient_no_retry():
    error=APIStatusError('private-secret',response=httpx.Response(401,request=httpx.Request('POST','https://example.com')),body=None)
    llm,client=service([error])
    with pytest.raises(LLMUnavailable,match='Groq API failure'): llm.generate_structured_response('system',{},NarrativeDraft)
    assert client.chat.completions.create.call_count==1

def test_server_error_retried():
    error=APIStatusError('unavailable',response=httpx.Response(503,request=httpx.Request('POST','https://example.com')),body=None)
    llm,client=service([error,response(VALID)])
    assert llm.generate_structured_response('system',{},NarrativeDraft).statements
    assert client.chat.completions.create.call_count==2

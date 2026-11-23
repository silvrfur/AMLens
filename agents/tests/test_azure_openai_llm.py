from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from pydantic import ValidationError
from openai import RateLimitError, APITimeoutError, APIStatusError
from agents.config import Settings
from agents.main import create_llm
from agents.services.azure_openai_llm import AzureOpenAILLM
from agents.services.llm import LLMUnavailable
from agents.agents.report_agent import NarrativeDraft

ENDPOINT = 'https://example-resource.openai.azure.com/'
VALID = '{"statements":["Review required."],"recommended_next_steps":["Review evidence."]}'
REQ = httpx.Request('POST', ENDPOINT)

def response(content): return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

def service(effects):
    client = Mock()
    client.chat.completions.create.side_effect = effects
    return AzureOpenAILLM(ENDPOINT, 'test-deployment', '2024-10-21', 'test-key', client=client, sleep=lambda _: None), client

def test_valid_json_and_sdk_arguments():
    llm, client = service([response(VALID)])
    assert llm.generate_structured_response('system', {}, NarrativeDraft).statements == ['Review required.']
    args = client.chat.completions.create.call_args.kwargs
    assert args['model'] == 'test-deployment'
    assert args['response_format'] == {'type': 'json_object'}
    assert args['temperature'] == 0
    assert 'test-key' not in str(args)

@pytest.mark.parametrize('body', ['not json', '{}', '{"statements":[]}', None])
def test_invalid_json_schema(body):
    llm, _ = service([response(body)])
    with pytest.raises(ValidationError): llm.generate_structured_response('system', {}, NarrativeDraft)

def test_rate_limit_retry():
    error = RateLimitError('rate', response=httpx.Response(429, request=REQ), body=None)
    llm, client = service([error, response(VALID)])
    llm.generate_structured_response('system', {}, NarrativeDraft)
    assert client.chat.completions.create.call_count == 2

def test_timeout_bounded():
    error = APITimeoutError(request=REQ)
    llm, client = service([error, error, error])
    with pytest.raises(LLMUnavailable, match='transient'): llm.generate_structured_response('system', {}, NarrativeDraft)
    assert client.chat.completions.create.call_count == 3

@pytest.mark.parametrize('status', [400, 401, 404])
def test_client_errors_not_retried(status):
    error = APIStatusError('private-secret', response=httpx.Response(status, request=REQ), body=None)
    llm, client = service([error])
    with pytest.raises(LLMUnavailable, match='Azure OpenAI API failure') as exc:
        llm.generate_structured_response('system', {}, NarrativeDraft)
    assert 'private-secret' not in str(exc.value)
    assert client.chat.completions.create.call_count == 1

def test_server_error_retried():
    error = APIStatusError('unavailable', response=httpx.Response(503, request=REQ), body=None)
    llm, client = service([error, response(VALID)])
    assert llm.generate_structured_response('system', {}, NarrativeDraft).statements
    assert client.chat.completions.create.call_count == 2

def test_requires_explicit_configuration():
    with pytest.raises(ValueError): AzureOpenAILLM('', '', '')

def test_keyless_entra_auth_uses_token_provider():
    provider = Mock(return_value='token')
    llm = AzureOpenAILLM(ENDPOINT, 'dep', '2024-10-21', token_provider=provider)
    assert llm.client._azure_ad_token_provider is provider
    llm.close()

@pytest.mark.parametrize('endpoint,version', [
    ('https://r.openai.azure.com/openai/v1/', '2024-10-21'),
    ('https://r.openai.azure.com/openai/v1', '2024-10-21'),
    ('https://r.openai.azure.com/', 'v1'),
])
def test_v1_endpoint_uses_openai_client(endpoint, version):
    from openai import OpenAI, AzureOpenAI
    llm = AzureOpenAILLM(endpoint, 'dep', version, 'k')
    assert isinstance(llm.client, OpenAI) and not isinstance(llm.client, AzureOpenAI)
    assert str(llm.client.base_url) == 'https://r.openai.azure.com/openai/v1/'
    llm.close()

def test_v1_keyless_uses_token_provider_as_api_key():
    provider = Mock(return_value='token')
    llm = AzureOpenAILLM('https://r.openai.azure.com/openai/v1/', 'dep', 'v1', token_provider=provider)
    assert str(llm.client.base_url).endswith('/openai/v1/')
    llm.close()

def test_factory_selects_provider():
    azure = create_llm(Settings(_env_file=None, use_mock_llm=False, azure_openai_endpoint=ENDPOINT,
                                azure_openai_deployment='dep', azure_openai_api_key='k'))
    assert isinstance(azure, AzureOpenAILLM) and azure.deployment == 'dep'
    azure.close()
    from agents.services.groq_llm import GroqLLM
    groq = create_llm(Settings(_env_file=None, use_mock_llm=False, llm_provider='groq', groq_api_key='k', groq_model='m'))
    assert isinstance(groq, GroqLLM)
    groq.close()

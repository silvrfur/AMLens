import pytest
from agents.config import Settings
from agents.main import create_services
from agents.services.groq_llm import GroqLLM

def test_offline_defaults():
    settings=Settings(_env_file=None)
    assert settings.use_mock_llm and settings.use_mock_rag and settings.use_mock_backend and settings.use_mock_service_bus
    assert settings.llm_provider=='groq'

def test_secret_configuration_not_printed():
    settings=Settings(_env_file=None,groq_api_key='super-secret',azure_service_bus_connection_string='azure-secret')
    assert 'super-secret' not in repr(settings)
    assert 'azure-secret' not in repr(settings)

def test_real_groq_requires_explicit_configuration():
    with pytest.raises(ValueError): GroqLLM('','')

def test_non_sqlite_url_rejected():
    with pytest.raises(ValueError): Settings(_env_file=None,database_url='unsupported:///database').database_path

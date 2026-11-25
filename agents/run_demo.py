"""Run from the ZIP root: python -m agents.run_demo (no credentials required)."""
import json
from pathlib import Path
from .config import Settings
from .main import create_services
from .mocks.mock_groq import MockGroqClient
from .schemas.messages import InvestigationMessage
from .worker.message_handler import MessageHandler
from .worker.service_bus_worker import drain_mock

def main():
    # Demo explicitly overrides environment so it never calls real services.
    settings = Settings(_env_file=None, database_url='sqlite:///' + str(Path(__file__).parent/'data'/'demo_runtime.db'),
        use_mock_llm=True, use_mock_rag=True, use_mock_backend=True, use_mock_service_bus=True, llm_provider='groq')
    for name, llm in [('normal', MockGroqClient()), ('corrected', MockGroqClient(fail_first=True)), ('incomplete', MockGroqClient(always_fail=True))]:
        services = create_services(settings, llm=llm)
        message = InvestigationMessage(alert_id='ALT-001', investigation_id='INV-DEMO-'+name)
        services.bus.send(message)
        print('Queue:', drain_mock(services.bus, MessageHandler(services.runner)))
        result = services.persistence.get(message.investigation_id)
        print('Scenario:', name)
        print('Agent execution sequence:', [r['agent_name'] for r in result['agent_execution_trace']])
        print(json.dumps(result, indent=2))
        print('Persistence confirmed:', result['execution_status'])
        services.close()

if __name__ == '__main__': main()

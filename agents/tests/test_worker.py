from unittest.mock import Mock, MagicMock
from agents.worker.message_handler import MessageHandler
from agents.worker.service_bus_worker import drain_mock
from agents.services.service_bus import MockServiceBus, MockMessage, AzureServiceBus

def test_persist_then_ack_idempotent(services,message):
    queue=services.bus
    queue.send(message); queue.send(message)
    assert drain_mock(queue,MessageHandler(services.runner))==['completed','completed']
    assert len(services.llm.calls)==1
    assert services.persistence.get(message.investigation_id)['execution_status']=='completed'

def test_retry_exhaustion():
    queue=MockServiceBus(); queue.pending.append(MockMessage('{"alert_id":"A","investigation_id":"I"}'))
    runner=Mock(); runner.run.side_effect=RuntimeError('failed')
    assert drain_mock(queue,MessageHandler(runner,3))==['retry','retry','dead_letter']
    assert not queue.completed and len(queue.dead_letters)==1

def test_transient_recovery():
    queue=MockServiceBus(); queue.pending.append(MockMessage('{"alert_id":"A","investigation_id":"I"}'))
    runner=Mock(); runner.run.side_effect=[RuntimeError(),{'execution_status':'completed'}]
    assert drain_mock(queue,MessageHandler(runner))==['retry','completed']

def test_invalid_message_dead_letter():
    queue=MockServiceBus(); queue.pending.append(MockMessage('{"decision":"close"}'))
    runner=Mock()
    assert drain_mock(queue,MessageHandler(runner))==['dead_letter']
    runner.run.assert_not_called()

def test_ack_failure_redelivery(services,message):
    receiver=Mock(); receiver.complete_message.side_effect=RuntimeError('lock lost')
    raw=MockMessage(message.model_dump_json())
    import pytest
    with pytest.raises(RuntimeError): MessageHandler(services.runner).handle(raw,receiver)
    assert MessageHandler(services.runner).handle(raw,services.bus)=='completed'
    assert len(services.llm.calls)==1

def test_azure_sender_sdk_contract(monkeypatch,message):
    import azure.servicebus
    client=MagicMock()
    monkeypatch.setattr(azure.servicebus.ServiceBusClient,'from_connection_string',lambda _:client)
    bus=AzureServiceBus('test-connection','test-queue')
    bus.send(message)
    sent=client.get_queue_sender.return_value.__enter__.return_value.send_messages.call_args.args[0]
    assert sent.message_id == message.investigation_id
    assert message.alert_id in str(sent)
    client.get_queue_sender.assert_called_once_with('test-queue')

def test_incomplete_is_persisted_before_ack(services,message):
    from agents.graph import InvestigationRunner
    from agents.mocks.mock_backend import MockBackendClient
    from agents.mocks.mock_groq import MockGroqClient
    runner=InvestigationRunner(MockBackendClient(services.persistence.db),services.rag,MockGroqClient(always_fail=True),services.persistence)
    services.bus.send(message)
    assert drain_mock(services.bus,MessageHandler(runner))==['completed']
    assert services.persistence.get(message.investigation_id)['execution_status']=='incomplete'
    assert len(services.bus.completed)==1

def test_worker_conflict_dead_letters(services,message):
    from agents.schemas.messages import InvestigationMessage
    services.runner.run(message)
    services.bus.send(InvestigationMessage(alert_id='ALT-002',investigation_id=message.investigation_id))
    assert drain_mock(services.bus,MessageHandler(services.runner))==['dead_letter']
    assert services.bus.dead_letters[0].dead_letter_reason=='InvestigationIdConflict'

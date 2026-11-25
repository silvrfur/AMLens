from collections import deque
from dataclasses import dataclass
from uuid import uuid4

@dataclass
class MockMessage:
    body: str
    delivery_count: int = 1
    settled: str | None = None
    dead_letter_reason: str | None = None

class MockServiceBus:
    def __init__(self):
        self.pending, self.completed, self.dead_letters = deque(), [], []
    def send(self, message):
        self.pending.append(MockMessage(message.model_dump_json()))
    def complete_message(self, message):
        message.settled = 'completed'; self.completed.append(message)
    def abandon_message(self, message):
        message.delivery_count += 1; self.pending.append(message)
    def dead_letter_message(self, message, reason, error_description=None):
        message.settled = 'dead_letter'; message.dead_letter_reason = reason
        self.dead_letters.append(message)
    def close(self): pass

# INTEGRATION POINT — shared Azure infrastructure: backend publishes the documented
# InvestigationMessage JSON to this queue. Configure RBAC/networking outside agents.
class AzureServiceBus:
    def __init__(self, connection_string, queue_name):
        from azure.servicebus import ServiceBusClient
        if not connection_string or not queue_name: raise ValueError('Azure configuration required')
        self.client = ServiceBusClient.from_connection_string(connection_string)
        self.queue_name = queue_name
    def send(self, message):
        from azure.servicebus import ServiceBusMessage
        with self.client.get_queue_sender(self.queue_name) as sender:
            sender.send_messages(ServiceBusMessage(message.model_dump_json(), message_id=message.investigation_id))
    def close(self): self.client.close()

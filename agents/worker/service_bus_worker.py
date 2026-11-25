from .message_handler import MessageHandler

def drain_mock(queue, handler):
    outcomes = []
    while queue.pending:
        outcomes.append(handler.handle(queue.pending.popleft(), queue))
    return outcomes

def run_azure_worker(bus, handler):
    from azure.servicebus import AutoLockRenewer
    # Single-message receive limits local contention; lock renewal spans bounded LLM calls.
    with bus.client, AutoLockRenewer(max_lock_renewal_duration=900) as renewer:
        with bus.client.get_queue_receiver(bus.queue_name, max_wait_time=5, prefetch_count=0) as receiver:
            while True:
                for message in receiver.receive_messages(max_message_count=1, max_wait_time=5):
                    renewer.register(receiver, message)
                    handler.handle(message, receiver)

def main():
    from ..main import create_services
    from ..config import Settings
    from ..schemas.messages import InvestigationMessage
    settings = Settings()
    services = create_services(settings)
    handler = MessageHandler(services.runner, settings.max_delivery_count)
    try:
        if settings.use_mock_service_bus:
            services.bus.send(InvestigationMessage(alert_id='ALT-001', investigation_id='INV-WORKER-DEMO'))
            print(drain_mock(services.bus, handler))
        else: run_azure_worker(services.bus, handler)
    finally: services.close()

if __name__ == '__main__': main()

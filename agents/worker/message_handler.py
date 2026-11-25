import logging
from pydantic import ValidationError
from ..schemas.messages import InvestigationMessage
from ..services.persistence import InvestigationConflict

log = logging.getLogger('traceiq.worker')

class MessageHandler:
    def __init__(self, runner, max_delivery_count=3):
        self.runner, self.max_delivery_count = runner, max_delivery_count

    def handle(self, message, receiver):
        try:
            body = message.body
            if not isinstance(body, (str, bytes)):
                body = b''.join(body)
            request = InvestigationMessage.model_validate_json(body)
        except (ValidationError, ValueError, TypeError):
            receiver.dead_letter_message(message, reason='InvalidMessage', error_description='Expected alert_id and investigation_id')
            return 'dead_letter'
        try:
            result = self.runner.run(request)
            if result['execution_status'] not in ('completed','incomplete'):
                raise RuntimeError('Nonterminal investigation')
        except InvestigationConflict:
            receiver.dead_letter_message(message, reason='InvestigationIdConflict')
            return 'dead_letter'
        except Exception as exc:
            log.warning('queue_failure type=%s investigation_id=%s', type(exc).__name__, request.investigation_id)
            if message.delivery_count >= self.max_delivery_count:
                receiver.dead_letter_message(message, reason='RetriesExhausted', error_description='Investigation processing failed')
                return 'dead_letter'
            receiver.abandon_message(message)
            return 'retry'
        # Settlement is deliberately outside the processing exception handler.
        # If it fails, broker redelivery reads the persisted result without rerunning agents.
        receiver.complete_message(message)
        return 'completed'

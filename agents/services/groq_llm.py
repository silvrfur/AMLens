import json
import time
from typing import Protocol, TypeVar
from pydantic import BaseModel
from groq import Groq, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError
from .audit_service import consume

T = TypeVar("T", bound=BaseModel)
class StructuredLLM(Protocol):
    def generate_structured_response(self, system_prompt: str, user_input: dict, response_schema: type[T]) -> T: ...

class LLMUnavailable(RuntimeError): pass

class GroqLLM:
    def __init__(self, api_key, model, timeout=30, client=None, sleep=time.sleep):
        if not api_key or not model:
            raise ValueError("Real Groq requires GROQ_API_KEY and GROQ_MODEL")
        # Disable SDK retries so every actual request is counted against the graph budget.
        self.client = client or Groq(api_key=api_key, timeout=timeout, max_retries=0)
        self.model, self.sleep = model, sleep

    def generate_structured_response(self, system_prompt, user_input, response_schema):
        messages = [
            {"role": "system", "content": system_prompt + " Return only JSON matching this schema: " + json.dumps(response_schema.model_json_schema())},
            {"role": "user", "content": json.dumps(user_input)},
        ]
        for attempt in range(3):
            consume("llm.generate")
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, temperature=0,
                    response_format={"type": "json_object"})
                return response_schema.model_validate_json(response.choices[0].message.content or "")
            except (RateLimitError, APIConnectionError, APITimeoutError):
                if attempt == 2: raise LLMUnavailable("Groq transient failure") from None
            except APIStatusError as exc:
                if exc.status_code < 500 or attempt == 2:
                    raise LLMUnavailable("Groq API failure") from None
            # No provider exceptions or prompt contents are logged.
            self.sleep(min(2 ** attempt, 4))

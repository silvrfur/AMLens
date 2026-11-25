from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class StructuredLLM(Protocol):
    def generate_structured_response(self, system_prompt: str, user_input: dict, response_schema: type[T]) -> T: ...

class LLMUnavailable(RuntimeError): pass

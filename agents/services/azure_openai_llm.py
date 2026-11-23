import json
import time
from openai import AzureOpenAI, OpenAI, RateLimitError, APIConnectionError, APIStatusError
from .audit_service import consume
from .llm import LLMUnavailable

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
V1_SUFFIX = "/openai/v1"

def uses_v1_api(endpoint, api_version):
    return api_version == "v1" or endpoint.rstrip("/").endswith(V1_SUFFIX)

def v1_base_url(endpoint):
    base = endpoint.rstrip("/")
    return (base if base.endswith(V1_SUFFIX) else base + V1_SUFFIX) + "/"

def _entra_token_provider():
    # Keyless auth: managed identity in Azure, `az login` / env credentials locally.
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    return get_bearer_token_provider(DefaultAzureCredential(), COGNITIVE_SERVICES_SCOPE)

class AzureOpenAILLM:
    """StructuredLLM backed by an Azure OpenAI chat deployment.

    Same contract as GroqLLM: JSON object mode, local Pydantic validation, temperature 0,
    at most three attempts for transient failures, each attempt charged to the tool budget.
    """
    def __init__(self, endpoint, deployment, api_version, api_key="", timeout=30,
                 client=None, sleep=time.sleep, token_provider=None):
        if not endpoint or not deployment or not api_version:
            raise ValueError("Azure OpenAI requires AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_VERSION")
        if client is None:
            # Disable SDK retries so every actual request is counted against the graph budget.
            if uses_v1_api(endpoint, api_version):
                # v1 API (<resource>/openai/v1/): standard OpenAI client, no api-version;
                # api_key accepts either the key or an Entra bearer-token callable.
                client = OpenAI(base_url=v1_base_url(endpoint), timeout=timeout, max_retries=0,
                                api_key=api_key or token_provider or _entra_token_provider())
            else:
                auth = {"api_key": api_key} if api_key else {"azure_ad_token_provider": token_provider or _entra_token_provider()}
                client = AzureOpenAI(azure_endpoint=endpoint, api_version=api_version,
                                     timeout=timeout, max_retries=0, **auth)
        self.client, self.deployment, self.sleep = client, deployment, sleep

    def close(self): self.client.close()

    def generate_structured_response(self, system_prompt, user_input, response_schema):
        messages = [
            {"role": "system", "content": system_prompt + " Return only JSON matching this schema: " + json.dumps(response_schema.model_json_schema())},
            {"role": "user", "content": json.dumps(user_input)},
        ]
        for attempt in range(3):
            consume("llm.generate")
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment, messages=messages, temperature=0,
                    response_format={"type": "json_object"})
                return response_schema.model_validate_json(response.choices[0].message.content or "")
            except (RateLimitError, APIConnectionError):  # includes APITimeoutError
                if attempt == 2: raise LLMUnavailable("Azure OpenAI transient failure") from None
            except APIStatusError as exc:
                # 4xx (auth, missing deployment, content filter) is not retried.
                if exc.status_code < 500 or attempt == 2:
                    raise LLMUnavailable("Azure OpenAI API failure") from None
            # No provider exceptions or prompt contents are logged.
            self.sleep(min(2 ** attempt, 4))

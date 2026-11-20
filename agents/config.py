from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    groq_api_key: str = Field(default="", repr=False)
    groq_model: str = ""
    database_url: str = "sqlite:///./data/synthetic_alerts.db"
    azure_service_bus_connection_string: str = Field(default="", repr=False)
    azure_service_bus_queue_name: str = ""
    llm_provider: str = "groq"
    use_mock_llm: bool = True
    use_mock_rag: bool = True
    use_mock_backend: bool = True
    use_mock_service_bus: bool = True
    rag_service_url: str = ""
    groq_timeout_seconds: float = Field(default=30, gt=0, le=60)
    max_delivery_count: int = Field(default=3, ge=1, le=10)
    lease_seconds: int = Field(default=900, ge=600)

    @property
    def database_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// database URLs are supported")
        return Path(self.database_url.removeprefix("sqlite:///"))

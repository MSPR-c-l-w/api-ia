from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_title: str = "HealthAI Coach API"
    api_version: str = "0.2.0"
    environment: str = "development"
    secret_key: str = "dev-secret-key"
    mongodb_uri: str = "mongodb://localhost:27017/healthai_coach"
    backend_api_key: str = "change-me"
    nutrition_huggingface_endpoint: str | None = None
    nutrition_huggingface_api_key: str | None = None
    nutrition_google_vision_endpoint: str | None = None
    nutrition_google_vision_api_key: str | None = None
    nutrition_provider_timeout_seconds: int = 5
    nutrition_llm_endpoint: str | None = None
    nutrition_llm_api_key: str | None = None
    nutrition_llm_timeout_seconds: int = 30
    port: int = 8000

    @property
    def skip_mongodb_on_startup(self) -> bool:
        return self.environment == "test"


settings = Settings()

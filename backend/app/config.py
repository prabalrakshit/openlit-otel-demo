from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "dev"
    VERSION: str = "1.0.0"
    TITLE: str = "Trip Planner Agent"
    SERVICE_NAME: str = "trip-planner-app"
    ALLOWED_ORIGINS: str = "http://localhost:3001"

    OPENAI_API_KEY: str = ""

    OTLP_ENDPOINT: str = "http://localhost:4318"
    OTLP_HEADERS: str = ""

    MAX_TOOL_CALLS: int = 4

    ENABLE_PII_REDACTION: bool = True
    ENABLE_INJECTION_DETECTION: bool = True
    ENABLE_TOPIC_GATING: bool = True
    ENABLE_OUTPUT_VALIDATION: bool = True

settings = Settings()
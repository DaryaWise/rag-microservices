from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # URL внутренних сервисов
    RETRIEVER_URL: str = "http://127.0.0.1:8001"
    REASONER_URL: str  = "http://127.0.0.1:8002"

    # Таймауты и ретраи
    HTTP_TIMEOUT_SEC: float = 10.0
    RETRIES: int = 2  # количество повторов при ошибках

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_", extra="ignore")

settings = Settings()

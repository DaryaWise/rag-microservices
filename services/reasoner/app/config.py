from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM режим
    USE_EXTERNAL_LLM: bool = False

    # Ollama локально
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "mistral"

    # Внешняя LLM (если USE_EXTERNAL_LLM=true)
    OPENAI_API_KEY: str | None = None

    # Параметры генерации
    MAX_TOKENS: int = 512
    TEMPERATURE: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", env_prefix="REASONER_", extra="ignore")

settings = Settings()

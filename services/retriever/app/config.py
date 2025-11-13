from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    DATA_DIR: str = "./data"
    VSTORE_DIR: str = "./vectorstore"

    # Поиск
    DEFAULT_TOP_K: int = 5
    RERANK_ENABLED: bool = False     # включим позже
    RERANK_TOP_N: int = 20

    # Чанкование
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RETRIEVER_", extra="ignore")

    def data_path(self) -> Path:
        return Path(self.DATA_DIR)

    def vstore_path(self) -> Path:
        return Path(self.VSTORE_DIR)

settings = Settings()

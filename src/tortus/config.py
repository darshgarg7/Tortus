"""Runtime configuration for Tortus."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str | None = Field(default=None, alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(
        default="2025-01-01-preview", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_embedding_deployment: str | None = Field(
        default=None, alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )

    tortus_llm_model: str = Field(default="gpt-4.1", alias="TORTUS_LLM_MODEL")
    tortus_embedding_provider: str = Field(default="local", alias="TORTUS_EMBEDDING_PROVIDER")
    tortus_embedding_model: str = Field(
        default="text-embedding-3-large",
        alias="TORTUS_EMBEDDING_MODEL",
    )
    tortus_data_dir: Path = Field(default=Path("data"), alias="TORTUS_DATA_DIR")
    tortus_cache_dir: Path = Field(default=Path(".tortus_cache"), alias="TORTUS_CACHE_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return get settings."""
    return Settings()

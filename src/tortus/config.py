"""Runtime configuration for Tortus."""

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_CONFIG_NAME = "tortus.toml"
USER_CONFIG_PATH = Path.home() / ".tortus" / "config.toml"

CONFIG_KEY_TO_FIELD = {
    "azure_openai_api_key": "azure_openai_api_key",
    "azure_openai_api_version": "azure_openai_api_version",
    "azure_openai_deployment": "azure_openai_deployment",
    "azure_openai_embedding_deployment": "azure_openai_embedding_deployment",
    "azure_openai_endpoint": "azure_openai_endpoint",
    "corpus": "tortus_corpus",
    "embedding_provider": "tortus_embedding_provider",
    "embedding_model": "tortus_embedding_model",
    "embedding_dimensions": "tortus_embedding_dimensions",
    "extraction_provider": "tortus_extraction_provider",
    "openai_api_key": "openai_api_key",
    "openai_base_url": "openai_base_url",
    "synthesis_provider": "tortus_synthesis_provider",
    "vector_backend": "tortus_vector_backend",
    "data_dir": "tortus_data_dir",
    "cache_dir": "tortus_cache_dir",
    "llm_model": "tortus_llm_model",
}


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str | None = Field(default=None, alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(
        default="2025-01-01-preview", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_embedding_deployment: str | None = Field(
        default=None, alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")

    tortus_llm_model: str = Field(default="gpt-4.1", alias="TORTUS_LLM_MODEL")
    tortus_corpus: str = Field(default="public-engineering", alias="TORTUS_CORPUS")
    tortus_extraction_provider: str = Field(default="auto", alias="TORTUS_EXTRACTION_PROVIDER")
    tortus_synthesis_provider: str = Field(default="auto", alias="TORTUS_SYNTHESIS_PROVIDER")
    tortus_embedding_provider: str = Field(default="local", alias="TORTUS_EMBEDDING_PROVIDER")
    tortus_embedding_model: str = Field(
        default="text-embedding-3-large",
        alias="TORTUS_EMBEDDING_MODEL",
    )
    tortus_embedding_dimensions: int | None = Field(
        default=None,
        alias="TORTUS_EMBEDDING_DIMENSIONS",
    )
    tortus_vector_backend: str = Field(default="exact", alias="TORTUS_VECTOR_BACKEND")
    tortus_data_dir: Path = Field(default=Path("data"), alias="TORTUS_DATA_DIR")
    tortus_cache_dir: Path = Field(default=Path(".tortus_cache"), alias="TORTUS_CACHE_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return runtime settings with env values overriding tortus.toml values."""
    project_values = {
        **project_config_values(USER_CONFIG_PATH),
        **project_config_values(project_config_path()),
    }
    env_aliases = configured_env_aliases()
    filtered_values = {
        key: value
        for key, value in project_values.items()
        if settings_alias_for_field(key) not in env_aliases
    }
    return Settings(**filtered_values)


def settings_with_overrides(
    settings: Settings,
    *,
    corpus: str | None = None,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    vector_backend: str | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    extraction_provider: str | None = None,
    synthesis_provider: str | None = None,
) -> Settings:
    """Return settings updated with explicit CLI-level overrides."""
    updates: dict[str, Any] = {}
    if corpus is not None:
        updates["tortus_corpus"] = corpus
    if data_dir is not None:
        updates["tortus_data_dir"] = data_dir
    if cache_dir is not None:
        updates["tortus_cache_dir"] = cache_dir
    if vector_backend is not None:
        updates["tortus_vector_backend"] = vector_backend
    if embedding_provider is not None:
        updates["tortus_embedding_provider"] = embedding_provider
    if embedding_model is not None:
        updates["tortus_embedding_model"] = embedding_model
    if extraction_provider is not None:
        updates["tortus_extraction_provider"] = extraction_provider
    if synthesis_provider is not None:
        updates["tortus_synthesis_provider"] = synthesis_provider
    return settings.model_copy(update=updates)


def project_config_path(start: Path | None = None) -> Path | None:
    """Return the nearest tortus.toml path by walking upward from the current directory."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        path = candidate / PROJECT_CONFIG_NAME
        if path.exists():
            return path
    return None


def project_config_values(path: Path | None) -> dict[str, Any]:
    """Load recognized Tortus settings from a project config file."""
    if path is None or not path.exists():
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    section = payload.get("tortus", payload)
    if not isinstance(section, dict):
        return {}
    values: dict[str, Any] = {}
    for key, value in section.items():
        field_name = CONFIG_KEY_TO_FIELD.get(str(key), str(key))
        if field_name in Settings.model_fields:
            values[field_name] = value
    return values


def configured_env_aliases(dotenv_path: Path = Path(".env")) -> set[str]:
    """Return environment aliases configured through OS env or the local .env file."""
    aliases = {str(key) for key in os.environ}
    if dotenv_path.exists():
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            aliases.add(stripped.split("=", 1)[0].strip())
    return aliases


def settings_alias_for_field(field_name: str) -> str:
    """Return the environment alias for a Settings field name."""
    field = Settings.model_fields[field_name]
    return str(field.alias or field_name)


def default_project_config() -> str:
    """Return the default tortus.toml content for a local project."""
    return "\n".join(
        [
            "[tortus]",
            'corpus = "workspace"',
            'data_dir = ".tortus/data"',
            'cache_dir = ".tortus/cache"',
            'embedding_provider = "local"',
            'embedding_model = "text-embedding-3-large"',
            'extraction_provider = "auto"',
            'synthesis_provider = "auto"',
            'vector_backend = "exact"',
            "",
        ]
    )


def user_config_values() -> dict[str, Any]:
    """Return values configured in the per-user Tortus config."""
    return project_config_values(USER_CONFIG_PATH)

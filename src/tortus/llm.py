"""LLM provider selection and deterministic JSON completion caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from openai import AzureOpenAI, OpenAI

from .config import Settings
from .embeddings import safe_namespace


@dataclass(frozen=True)
class LLMProvider:
    """A configured chat-completion provider."""

    name: str
    model: str
    client: AzureOpenAI | OpenAI

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Return a JSON object from a chat-completion response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        return cast(dict[str, Any], json.loads(content))


def llm_credentials_available(settings: Settings) -> bool:
    """Return whether any supported LLM provider is configured."""
    return llm_provider_name(settings) is not None


def llm_provider_name(settings: Settings) -> str | None:
    """Return the preferred configured LLM provider name."""
    if (
        settings.azure_openai_endpoint
        and settings.azure_openai_api_key
        and settings.azure_openai_deployment
    ):
        return "azure"
    if settings.openai_api_key:
        return "openai"
    return None


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Build the preferred LLM provider, or None when no credentials are configured."""
    provider_name = llm_provider_name(settings)
    if provider_name == "azure":
        return LLMProvider(
            name="azure",
            model=str(settings.azure_openai_deployment),
            client=AzureOpenAI(
                azure_endpoint=str(settings.azure_openai_endpoint),
                api_key=str(settings.azure_openai_api_key),
                api_version=settings.azure_openai_api_version,
            ),
        )
    if provider_name == "openai":
        client = (
            OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
            if settings.openai_base_url
            else OpenAI(api_key=settings.openai_api_key)
        )
        return LLMProvider(name="openai", model=settings.tortus_llm_model, client=client)
    return None


def provider_allowed(settings: Settings, purpose: str) -> bool:
    """Return whether a provider setting allows API-backed work for a purpose."""
    configured = (
        settings.tortus_extraction_provider
        if purpose == "extraction"
        else settings.tortus_synthesis_provider
    ).lower()
    return configured in {"auto", "openai", "azure", "llm"}


def quality_mode(settings: Settings, purpose: str) -> str:
    """Return a user-facing quality mode label for a purpose."""
    if provider_allowed(settings, purpose):
        provider = llm_provider_name(settings)
        if provider:
            return f"llm-{provider}"
    return "deterministic-local"


def cached_json_completion(
    settings: Settings,
    *,
    namespace: str,
    cache_parts: list[str],
    system: str,
    user: str,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Return a cached JSON completion for deterministic demos and repeated runs."""
    cache_dir = settings.tortus_cache_dir / "llm" / safe_namespace(namespace)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{completion_cache_key(cache_parts)}.json"
    if path.exists():
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    payload = provider.complete_json(system=system, user=user)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def completion_cache_key(parts: list[str]) -> str:
    """Return a stable cache key for an LLM request."""
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()


def user_config_path() -> Path:
    """Return the local per-user Tortus config path."""
    return Path.home() / ".tortus" / "config.toml"

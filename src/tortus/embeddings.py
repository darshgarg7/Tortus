"""Embedding providers and deterministic embedding cache."""

import hashlib
import json
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from openai import AzureOpenAI

from .config import Settings


class EmbeddingProvider(Protocol):
    """Represent EmbeddingProvider data."""

    dimensions: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized embeddings with shape (len(texts), dimensions)."""


class LocalHashEmbeddingProvider:
    """Deterministic local embeddings for tests, demos, and offline development."""

    def __init__(self, dimensions: int = 384) -> None:
        """Initialize the local embedding dimensionality."""
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return embed."""
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                matrix[row, bucket] += sign
        return normalize(matrix)


class AzureOpenAIEmbeddingProvider:
    """Represent AzureOpenAIEmbeddingProvider data."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Azure OpenAI embedding client."""
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise ValueError("Azure OpenAI endpoint and API key are required for embeddings")
        if not settings.azure_openai_embedding_deployment:
            raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required for Azure embeddings")
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.model = settings.azure_openai_embedding_deployment
        self.dimensions = 0

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return embed."""
        response = self.client.embeddings.create(model=self.model, input=texts)
        matrix = np.array([item.embedding for item in response.data], dtype=np.float32)
        self.dimensions = matrix.shape[1]
        return normalize(matrix)


class CachedEmbeddingProvider:
    """Represent CachedEmbeddingProvider data."""

    def __init__(self, provider: EmbeddingProvider, cache_dir: Path) -> None:
        """Initialize the embedding provider cache."""
        self.provider = provider
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dimensions = provider.dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return embed."""
        rows: list[np.ndarray] = []
        missing: list[str] = []
        missing_keys: list[str] = []
        for text in texts:
            key = cache_key(text)
            path = self.cache_dir / f"{key}.json"
            if path.exists():
                cached = json.loads(path.read_text(encoding="utf-8"))
                rows.append(np.array(cached, dtype=np.float32))
            else:
                missing.append(text)
                missing_keys.append(key)
        if missing:
            embedded = self.provider.embed(missing)
            self.dimensions = embedded.shape[1]
            for key, vector in zip(missing_keys, embedded, strict=True):
                (self.cache_dir / f"{key}.json").write_text(
                    json.dumps(vector.astype(float).tolist()),
                    encoding="utf-8",
                )
                rows.append(vector)
        matrix = np.vstack(rows) if rows else np.zeros((0, self.dimensions), dtype=np.float32)
        return normalize(matrix)


def cache_key(text: str) -> str:
    """Return cache key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(matrix: np.ndarray) -> np.ndarray:
    """Normalize normalize."""
    if matrix.size == 0:
        return matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return cast(np.ndarray, (matrix / norms).astype(np.float32))


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build build embedding provider."""
    provider_name = settings.tortus_embedding_provider.lower()
    if provider_name == "azure":
        provider: EmbeddingProvider = AzureOpenAIEmbeddingProvider(settings)
    elif provider_name == "local":
        provider = LocalHashEmbeddingProvider()
    else:
        raise ValueError(f"unknown embedding provider: {settings.tortus_embedding_provider}")
    return CachedEmbeddingProvider(provider, settings.tortus_cache_dir / "embeddings")

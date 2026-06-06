"""Embedding providers and deterministic embedding cache."""

import hashlib
import json
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from openai import AzureOpenAI, OpenAI

from .config import Settings


class EmbeddingProvider(Protocol):
    """Protocol implemented by embedding providers."""

    dimensions: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized embeddings with shape (len(texts), dimensions)."""


class LocalHashEmbeddingProvider:
    """Deterministic local embeddings for tests, demos, and offline development."""

    def __init__(self, dimensions: int = 384) -> None:
        """Initialize the local embedding dimensionality."""
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts with deterministic signed token hashing."""
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                matrix[row, bucket] += sign
        return normalize(matrix)


class AzureOpenAIEmbeddingProvider:
    """Azure OpenAI embedding adapter."""

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
        """Embed texts with the configured Azure OpenAI deployment."""
        response = self.client.embeddings.create(model=self.model, input=texts)
        matrix = np.array([item.embedding for item in response.data], dtype=np.float32)
        self.dimensions = matrix.shape[1]
        return normalize(matrix)


class OpenAIEmbeddingProvider:
    """OpenAI embeddings API adapter."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the OpenAI embeddings client."""
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        if settings.openai_base_url:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.tortus_embedding_model
        self.dimensions_requested = settings.tortus_embedding_dimensions
        self.dimensions = settings.tortus_embedding_dimensions or 0

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts with the configured OpenAI embedding model."""
        if self.dimensions_requested is not None:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions_requested,
            )
        else:
            response = self.client.embeddings.create(model=self.model, input=texts)
        matrix = np.array([item.embedding for item in response.data], dtype=np.float32)
        self.dimensions = matrix.shape[1]
        return normalize(matrix)


class CachedEmbeddingProvider:
    """File-backed embedding cache wrapper."""

    def __init__(self, provider: EmbeddingProvider, cache_dir: Path, namespace: str) -> None:
        """Initialize the embedding provider cache."""
        self.provider = provider
        self.cache_dir = cache_dir / safe_namespace(namespace)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dimensions = provider.dimensions

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return cached embeddings, computing and saving misses."""
        rows: list[np.ndarray | None] = []
        missing: list[str] = []
        missing_keys: list[str] = []
        missing_indexes: list[int] = []
        for index, text in enumerate(texts):
            key = cache_key(text)
            path = self.cache_dir / f"{key}.json"
            if path.exists():
                cached = json.loads(path.read_text(encoding="utf-8"))
                rows.append(np.array(cached, dtype=np.float32))
            else:
                rows.append(None)
                missing.append(text)
                missing_keys.append(key)
                missing_indexes.append(index)
        if missing:
            embedded = self.provider.embed(missing)
            self.dimensions = embedded.shape[1]
            for index, key, vector in zip(missing_indexes, missing_keys, embedded, strict=True):
                (self.cache_dir / f"{key}.json").write_text(
                    json.dumps(vector.astype(float).tolist()),
                    encoding="utf-8",
                )
                rows[index] = vector
        completed = [row for row in rows if row is not None]
        matrix = (
            np.vstack(completed)
            if completed
            else np.zeros((0, self.dimensions), dtype=np.float32)
        )
        if matrix.ndim == 2:
            self.dimensions = matrix.shape[1]
        return normalize(matrix)


def cache_key(text: str) -> str:
    """Return cache key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_namespace(value: str) -> str:
    """Return a filesystem-safe cache namespace."""
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)[:96]


def normalize(matrix: np.ndarray) -> np.ndarray:
    """Return row-wise L2-normalized vectors."""
    if matrix.size == 0:
        return matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return cast(np.ndarray, (matrix / norms).astype(np.float32))


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the configured embedding provider with a local cache."""
    provider_name = settings.tortus_embedding_provider.lower()
    if provider_name == "azure":
        provider: EmbeddingProvider = AzureOpenAIEmbeddingProvider(settings)
        namespace = f"azure-{settings.azure_openai_embedding_deployment}"
    elif provider_name == "openai":
        provider = OpenAIEmbeddingProvider(settings)
        dimensions = settings.tortus_embedding_dimensions or "default"
        namespace = f"openai-{settings.tortus_embedding_model}-{dimensions}"
    elif provider_name == "local":
        provider = LocalHashEmbeddingProvider()
        namespace = f"local-{provider.dimensions}"
    else:
        raise ValueError(f"unknown embedding provider: {settings.tortus_embedding_provider}")
    return CachedEmbeddingProvider(provider, settings.tortus_cache_dir / "embeddings", namespace)

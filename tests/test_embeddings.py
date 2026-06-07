import numpy as np

from tortus.config import Settings
from tortus.embeddings import (
    AzureOpenAIEmbeddingProvider,
    CachedEmbeddingProvider,
    LocalHashEmbeddingProvider,
    OpenAIEmbeddingProvider,
)


def test_local_hash_embeddings_are_normalized() -> None:
    provider = LocalHashEmbeddingProvider(dimensions=32)
    vectors = provider.embed(["token migration", "trace propagation"])
    norms = np.linalg.norm(vectors, axis=1)
    assert vectors.shape == (2, 32)
    assert np.allclose(norms, 1.0)


def test_azure_embedding_provider_uses_configured_client(monkeypatch) -> None:
    class FakeItem:
        def __init__(self, embedding: list[float]) -> None:
            self.embedding = embedding

    class FakeResponse:
        data = [FakeItem([3.0, 4.0]), FakeItem([0.0, 5.0])]

    class FakeEmbeddings:
        def create(self, model: str, input: list[str]) -> FakeResponse:
            assert model == "embeddings"
            assert input == ["one", "two"]
            return FakeResponse()

    class FakeClient:
        embeddings = FakeEmbeddings()

    def fake_azure_openai(**kwargs: object) -> FakeClient:
        assert kwargs["azure_endpoint"] == "https://example.openai.azure.com"
        assert kwargs["api_key"] == "key"
        return FakeClient()

    monkeypatch.setattr("tortus.embeddings.AzureOpenAI", fake_azure_openai)
    settings = Settings(
        AZURE_OPENAI_ENDPOINT="https://example.openai.azure.com",
        AZURE_OPENAI_API_KEY="key",
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT="embeddings",
    )
    provider = AzureOpenAIEmbeddingProvider(settings)
    vectors = provider.embed(["one", "two"])

    assert vectors.shape == (2, 2)
    assert provider.dimensions == 2
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_openai_embedding_provider_uses_api_model_and_dimensions(monkeypatch) -> None:
    class FakeItem:
        def __init__(self, embedding: list[float]) -> None:
            self.embedding = embedding

    class FakeResponse:
        data = [FakeItem([1.0, 0.0, 0.0]), FakeItem([0.0, 3.0, 4.0])]

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> FakeResponse:
            assert kwargs["model"] == "text-embedding-3-small"
            assert kwargs["input"] == ["one", "two"]
            assert kwargs["dimensions"] == 3
            return FakeResponse()

    class FakeClient:
        embeddings = FakeEmbeddings()

    def fake_openai(**kwargs: object) -> FakeClient:
        assert kwargs["api_key"] == "key"
        assert kwargs["base_url"] == "https://api.example.test/v1"
        return FakeClient()

    monkeypatch.setattr("tortus.embeddings.OpenAI", fake_openai)
    settings = Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://api.example.test/v1",
        TORTUS_EMBEDDING_MODEL="text-embedding-3-small",
        TORTUS_EMBEDDING_DIMENSIONS=3,
    )
    provider = OpenAIEmbeddingProvider(settings)
    vectors = provider.embed(["one", "two"])

    assert vectors.shape == (2, 3)
    assert provider.dimensions == 3
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_cached_embeddings_preserve_input_order_and_namespace(tmp_path) -> None:
    class ZeroDimProvider:
        dimensions = 0

        def embed(self, texts: list[str]) -> np.ndarray:
            raise AssertionError("cache hit should not call the wrapped provider")

    provider = CachedEmbeddingProvider(
        LocalHashEmbeddingProvider(dimensions=8),
        tmp_path,
        "local-8",
    )
    first = provider.embed(["alpha", "beta"])
    second = provider.embed(["beta", "gamma", "alpha"])
    cache_only = CachedEmbeddingProvider(ZeroDimProvider(), tmp_path, "local-8")
    cached = cache_only.embed(["alpha", "beta"])

    assert np.allclose(second[0], first[1])
    assert np.allclose(second[2], first[0])
    assert np.allclose(cached, first)
    assert cache_only.dimensions == 8
    assert (tmp_path / "local-8").exists()

import numpy as np

from tortus.config import Settings
from tortus.embeddings import AzureOpenAIEmbeddingProvider, LocalHashEmbeddingProvider


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

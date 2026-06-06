from fastapi.testclient import TestClient

from tortus.api import create_app
from tortus.config import Settings


def test_api_graphql_dashboard_and_summary(tmp_path) -> None:
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="engineering",
    )
    with TestClient(create_app(settings)) as client:
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "Tortus Query Lab" in dashboard.text

        graph = client.get("/api/graph")
        assert graph.status_code == 200
        graph_payload = graph.json()
        assert graph_payload["nodes"]
        assert graph_payload["edges"]

        summary = client.get("/api/eval-summary")
        assert summary.status_code == 200
        assert "strategies" in summary.json()

        response = client.post(
            "/graphql",
            json={
                "query": """
                query($q: String!) {
                  answer(query: $q) {
                    answer
                    confidence
                    budget {
                      nodesVisited
                      candidatesConsidered
                      prunedEdges
                      lexicalSupport
                    }
                    reasoningPath {
                      fromNode
                      toNode
                      edgeType
                      score
                      reason
                      matchedTerms
                      scoreComponents { key value }
                    }
                    trace {
                      queryTerms
                      seedHits { nodeId score matchedTerms }
                      prunedCandidates { fromNode toNode edgeType reason score }
                      portalDecisions { fromNode toNode selected reason }
                      unsupportedClaims { text supported }
                    }
                    evidence { uri text }
                  }
                }
                """,
                "variables": {
                    "q": "How did token migration connect authentication and tracing?"
                },
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "errors" not in payload
        answer = payload["data"]["answer"]
        assert answer["confidence"] > 0
        assert answer["evidence"]
        assert answer["trace"]["seedHits"]
        assert "prunedCandidates" in answer["trace"]
        assert answer["budget"]["candidatesConsidered"] >= answer["budget"]["nodesVisited"] - 1

        json_response = client.post(
            "/api/query",
            json={"query": "How did token migration connect authentication and tracing?"},
        )
        assert json_response.status_code == 200
        json_payload = json_response.json()
        assert json_payload["trace"]["seed_hits"]
        assert "pruned_candidates" in json_payload["trace"]

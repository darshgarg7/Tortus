"""FastAPI, GraphQL, and dashboard routes for Tortus."""

from collections import defaultdict
from pathlib import Path

import strawberry
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from strawberry.fastapi import GraphQLRouter

from .config import get_settings
from .eval import EvalReport
from .models import ConceptNode, SemanticEdge, TraversalPolicy
from .pipeline import data_paths, load_engine, load_nodes

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


@strawberry.type
class EvidenceType:
    """GraphQL representation of a source-backed evidence span."""

    uri: str
    start: int
    end: int
    text: str


@strawberry.type
class ConceptType:
    """GraphQL representation of a semantic graph node."""

    id: str
    label: str
    text: str
    domain: str
    theta: float | None
    phi: float | None
    evidence: list[EvidenceType]


@strawberry.input
class AnswerPolicyInput:
    """GraphQL input for bounded traversal controls."""

    max_hops: int = 3
    max_nodes: int = 64
    max_portal_hops: int = 8
    max_ms: int = 1500
    local_only: bool = False
    explain_hops: bool = True


@strawberry.type
class BudgetType:
    """GraphQL representation of retrieval budget telemetry."""

    elapsed_ms: float
    nodes_visited: int
    hops_taken: int
    portal_hops: int
    shard_fanout: int
    shard_crossings: int
    tokens_estimated: int
    truncated: bool


@strawberry.type
class HopType:
    """GraphQL representation of a reasoning-path hop."""

    from_node: str
    to_node: str
    edge_type: str
    weight: float


@strawberry.type
class AnswerType:
    """GraphQL answer payload with evidence and retrieval telemetry."""

    answer: str
    confidence: float
    budget: BudgetType
    warnings: list[str]
    reasoning_path: list[HopType]
    evidence: list[EvidenceType]


@strawberry.type
class Query:
    """Top-level Tortus GraphQL query fields."""

    @strawberry.field
    def concept(self, id: str) -> ConceptType | None:
        """Return a concept node by id."""
        engine = load_engine(get_settings())
        node = engine.graph.get_node(id)
        if node is None:
            return None
        return to_concept_type(node)

    @strawberry.field
    def concepts(self) -> list[ConceptType]:
        """Return all concept nodes in the current graph."""
        return [to_concept_type(node) for node in load_nodes(get_settings())]

    @strawberry.field
    def answer(self, query: str, policy: AnswerPolicyInput | None = None) -> AnswerType:
        """Answer a query with bounded graph traversal and evidence paths."""
        policy = policy or AnswerPolicyInput()
        result = load_engine(get_settings()).answer(
            query,
            TraversalPolicy(
                max_hops=policy.max_hops,
                max_nodes=policy.max_nodes,
                max_portal_hops=policy.max_portal_hops,
                max_ms=policy.max_ms,
                local_only=policy.local_only,
                explain_hops=policy.explain_hops,
            ),
        )
        return AnswerType(
            answer=result.answer,
            confidence=result.confidence,
            budget=BudgetType(**result.budget.model_dump()),
            warnings=result.warnings,
            reasoning_path=[
                HopType(
                    from_node=hop.from_node,
                    to_node=hop.to_node,
                    edge_type=hop.edge_type.value,
                    weight=hop.weight,
                )
                for hop in result.reasoning_path
            ],
            evidence=[EvidenceType(**span.model_dump()) for span in result.evidence],
        )


def to_concept_type(node: ConceptNode) -> ConceptType:
    """Convert an internal concept model to the GraphQL DTO."""
    domain = node.memberships[0].subgraph if node.memberships else "unknown"
    return ConceptType(
        id=node.id,
        label=node.label,
        text=node.text,
        domain=domain,
        theta=node.torus.theta if node.torus else None,
        phi=node.torus.phi if node.torus else None,
        evidence=[EvidenceType(**span.model_dump()) for span in node.evidence],
    )


def node_payload(node: ConceptNode) -> dict[str, object]:
    """Return a JSON-safe node payload for dashboard visualization."""
    return {
        "id": node.id,
        "label": node.label,
        "domain": node.memberships[0].subgraph if node.memberships else "unknown",
        "theta": node.torus.theta if node.torus else 0.0,
        "phi": node.torus.phi if node.torus else 0.0,
        "source": node.evidence[0].uri if node.evidence else "",
        "text": node.text,
    }


def edge_payload(edge: SemanticEdge) -> dict[str, object]:
    """Return a JSON-safe edge payload for dashboard visualization."""
    return {
        "id": edge.id,
        "source": edge.source,
        "target": edge.target,
        "edgeType": edge.edge_type.value,
        "weight": edge.weight,
    }


def eval_summary_payload() -> list[dict[str, object]]:
    """Load the latest eval report and summarize it by strategy."""
    settings = get_settings()
    root = data_paths(settings)["root"]
    report_path = root / "eval" / "benchmark.json"
    if not report_path.exists():
        report_path = root / "eval" / "full.json"
    if not report_path.exists():
        report_path = root / "eval" / "smoke.json"
    if not report_path.exists():
        return []

    report = EvalReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[float]] = defaultdict(list)
    source_by_strategy: dict[str, list[float]] = defaultdict(list)
    path_by_strategy: dict[str, list[float]] = defaultdict(list)
    latency_by_strategy: dict[str, list[float]] = defaultdict(list)
    portal_by_strategy: dict[str, list[float]] = defaultdict(list)
    fanout_by_strategy: dict[str, list[float]] = defaultdict(list)
    for row in report.rows:
        grouped[row.strategy].append(1.0 if row.passed else 0.0)
        source_by_strategy[row.strategy].append(row.source_recall)
        path_by_strategy[row.strategy].append(row.path_recall)
        latency_by_strategy[row.strategy].append(row.latency_ms)
        portal_by_strategy[row.strategy].append(float(row.portal_hops))
        fanout_by_strategy[row.strategy].append(float(row.shard_fanout))

    return [
        {
            "strategy": strategy,
            "pass": average(grouped[strategy]),
            "source": average(source_by_strategy[strategy]),
            "path": average(path_by_strategy[strategy]),
            "latencyMs": average(latency_by_strategy[strategy]),
            "portalHops": average(portal_by_strategy[strategy]),
            "shardFanout": average(fanout_by_strategy[strategy]),
        }
        for strategy in sorted(grouped)
    ]


def average(values: list[float]) -> float:
    """Return the arithmetic mean for a list of floats."""
    return sum(values) / len(values) if values else 0.0


def create_app() -> FastAPI:
    """Create the Tortus FastAPI app with GraphQL and dashboard routes."""
    fastapi_app = FastAPI(title="Tortus")
    schema = strawberry.Schema(query=Query)
    fastapi_app.include_router(GraphQLRouter(schema), prefix="/graphql")
    fastapi_app.mount(
        "/static",
        StaticFiles(directory=str(PACKAGE_DIR / "static")),
        name="static",
    )

    @fastapi_app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        """Serve the server-rendered dashboard shell."""
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "Tortus Query Lab",
                "default_query": (
                    "How did the token migration incident connect authentication and tracing?"
                ),
            },
        )

    @fastapi_app.get("/api/graph")
    async def graph_data() -> dict[str, list[dict[str, object]]]:
        """Return graph nodes and edges for the Plotly dashboard."""
        engine = load_engine(get_settings())
        return {
            "nodes": [node_payload(node) for node in engine.graph.list_nodes()],
            "edges": [edge_payload(edge) for edge in engine.graph.list_edges()],
        }

    @fastapi_app.get("/api/eval-summary")
    async def eval_summary() -> dict[str, list[dict[str, object]]]:
        """Return the latest strategy comparison summary."""
        return {"strategies": eval_summary_payload()}

    return fastapi_app

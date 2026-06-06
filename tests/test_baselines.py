from tortus.baselines import STRATEGIES, tokenize
from tortus.eval import parse_strategies, questions_for_suite


def test_tokenize_removes_question_words() -> None:
    assert tokenize("How did token migration connect tracing?") == [
        "token",
        "migration",
        "connect",
        "tracing",
    ]


def test_parse_strategies_all_and_subset() -> None:
    assert parse_strategies("all") == STRATEGIES
    assert parse_strategies("bm25,vector_only") == ("bm25_local", "vector_only_local")
    assert {
        "hybrid_dense_bm25_local",
        "community_summary_local",
        "bounded_agentic_local",
    }.issubset(set(STRATEGIES))


def test_full_suite_includes_smoke_and_golden_questions() -> None:
    assert len(questions_for_suite("full")) > len(questions_for_suite("smoke"))
    assert len(questions_for_suite("stress")) >= len(questions_for_suite("golden"))
    assert len(questions_for_suite("benchmark")) > len(questions_for_suite("full"))

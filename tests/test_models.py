import pytest

from tortus.models import EvidenceSpan, TraversalPolicy


def test_evidence_span_rejects_negative_range() -> None:
    with pytest.raises(ValueError):
        EvidenceSpan(uri="test://doc", start=10, end=2, text="bad")


def test_traversal_policy_has_bounded_defaults() -> None:
    policy = TraversalPolicy()
    assert policy.max_hops == 3
    assert policy.max_nodes == 64
    assert policy.max_portal_hops == 5
    assert policy.explain_hops is True

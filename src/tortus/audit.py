"""Human audit import/export helpers for benchmark labels."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .eval import EvalQuestion, questions_for_suite


class AuditRecord(BaseModel):
    """One human-reviewable benchmark label record."""

    id: str
    suite: str
    question: str
    expected_terms: list[str]
    expected_sources: list[str] = Field(default_factory=list)
    expected_evidence_uris: list[str] = Field(default_factory=list)
    expected_edge_types: list[str] = Field(default_factory=list)
    expected_path_labels: list[str] = Field(default_factory=list)
    expect_answer: bool = True
    status: str = "pending"
    auditor: str = ""
    reviewed_at: str = ""
    notes: str = ""

    def model_post_init(self, __context: object) -> None:
        """Keep old and reviewer-friendly audit label fields in sync."""
        if not self.expected_sources and self.expected_evidence_uris:
            self.expected_sources = list(self.expected_evidence_uris)
        if not self.expected_evidence_uris and self.expected_sources:
            self.expected_evidence_uris = list(self.expected_sources)
        if not self.expected_edge_types and self.expected_path_labels:
            self.expected_edge_types = list(self.expected_path_labels)
        if not self.expected_path_labels and self.expected_edge_types:
            self.expected_path_labels = list(self.expected_edge_types)


def export_audit_suite(suite: str, out: Path) -> int:
    """Export a suite as JSONL records ready for human audit."""
    records = [record_from_question(question) for question in questions_for_suite(suite)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(record.model_dump_json() for record in records) + "\n",
        encoding="utf-8",
    )
    return len(records)


def import_audit_records(path: Path, out: Path | None = None) -> int:
    """Validate and persist audited JSONL records."""
    records: list[AuditRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(AuditRecord.model_validate_json(line))
    target = out or Path("data/audits") / f"{path.stem}.imported.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(record.model_dump_json() for record in records) + "\n",
        encoding="utf-8",
    )
    return len(records)


def audit_status_by_question(path: Path) -> dict[str, str]:
    """Load audit status labels from an imported JSONL audit file."""
    if not path.exists():
        return {}
    statuses: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = AuditRecord.model_validate_json(line)
            statuses[record.id] = record.status
    return statuses


def record_from_question(question: EvalQuestion) -> AuditRecord:
    """Convert an eval question into an editable audit record."""
    return AuditRecord(
        id=question.id,
        suite=question.suite,
        question=question.question,
        expected_terms=list(question.expected_terms),
        expected_sources=list(question.expected_sources),
        expected_evidence_uris=list(question.expected_sources),
        expected_edge_types=list(question.expected_edge_types),
        expected_path_labels=list(question.expected_edge_types),
        expect_answer=question.expect_answer,
        status="pending",
    )


def write_audit_summary(records_path: Path, out: Path) -> None:
    """Write a compact JSON summary for an imported audit file."""
    counts: dict[str, int] = {}
    for line in records_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            status = AuditRecord.model_validate_json(line).status
            counts[status] = counts.get(status, 0) + 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"statuses": counts}, indent=2) + "\n", encoding="utf-8")

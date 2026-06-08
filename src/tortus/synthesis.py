"""Action-plan synthesis for user-facing Tortus answers."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel, Field

from .config import Settings
from .llm import build_llm_provider, cached_json_completion, provider_allowed, quality_mode
from .traversal import SynthesizedAnswer

ACTION_PLAN_SCHEMA_VERSION = "action-plan-v1"


class LLMActionPlan(BaseModel):
    """Schema for LLM-polished diagnosis and remediation output."""

    diagnosis: str = Field(min_length=1, max_length=1400)
    root_cause_path: list[str] = Field(default_factory=list, max_length=8)
    recommended_actions: list[str] = Field(default_factory=list, max_length=8)
    missing_evidence: list[str] = Field(default_factory=list, max_length=8)


class LLMActionPlanEnhancer:
    """Polish deterministic evidence synthesis with a cached LLM action plan."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the enhancer from runtime settings."""
        self.settings = settings
        self.provider = build_llm_provider(settings)
        self.quality_mode = quality_mode(settings, "synthesis")

    def enhance(self, query: str, synthesized: SynthesizedAnswer) -> SynthesizedAnswer:
        """Return a schema-validated action plan grounded in selected evidence."""
        if self.provider is None or not synthesized.evidence:
            return synthesized
        system = (
            "You produce concise incident-analysis action plans. Use only the cited evidence. "
            "Do not invent services, causes, metrics, or fixes that are not supported by the "
            "evidence. Return only JSON with diagnosis, root_cause_path, recommended_actions, "
            "and missing_evidence."
        )
        evidence_lines = [
            f"[{index}] {span.uri} {span.start}-{span.end}: {span.text}"
            for index, span in enumerate(synthesized.evidence[:8], 1)
        ]
        user = "\n".join(
            [
                f"schema_version: {ACTION_PLAN_SCHEMA_VERSION}",
                f"question: {query}",
                f"draft_answer: {synthesized.answer}",
                "evidence:",
                *evidence_lines,
            ]
        )
        try:
            payload = cached_json_completion(
                self.settings,
                namespace="synthesis",
                cache_parts=[
                    ACTION_PLAN_SCHEMA_VERSION,
                    self.provider.name,
                    self.provider.model,
                    query,
                    "\n".join(evidence_lines),
                ],
                system=system,
                user=user,
                provider=self.provider,
            )
            plan = LLMActionPlan.model_validate(payload)
        except Exception:  # pragma: no cover - external provider fallback
            return synthesized
        return replace(
            synthesized,
            diagnosis=plan.diagnosis,
            root_cause_path=plan.root_cause_path or synthesized.root_cause_path,
            recommended_actions=plan.recommended_actions or synthesized.recommended_actions,
            missing_evidence=plan.missing_evidence or synthesized.missing_evidence,
            quality_mode=self.quality_mode,
        )


def build_action_plan_enhancer(settings: Settings) -> LLMActionPlanEnhancer | None:
    """Return an LLM action-plan enhancer when synthesis settings allow it."""
    if not provider_allowed(settings, "synthesis"):
        return None
    if build_llm_provider(settings) is None:
        return None
    return LLMActionPlanEnhancer(settings)

from backend.roadmap_engine.services import goal_intelligence_service
from backend.roadmap_engine.services.agent_models import ExtractionResult


def run(*, evidence_records: list[dict]) -> ExtractionResult:
    evidence_summary = goal_intelligence_service._summarize_evidence(evidence_records)  # noqa: SLF001
    return ExtractionResult(evidence_summary=evidence_summary)

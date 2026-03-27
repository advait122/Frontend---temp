from backend.roadmap_engine.services import goal_intelligence_service
from backend.roadmap_engine.services.agent_models import ResearchResult


def run(*, role_intent: dict) -> ResearchResult:
    evidence_records = goal_intelligence_service._collect_evidence_records(role_intent)  # noqa: SLF001
    source_summary = {
        "record_count": len(evidence_records),
        "live_job_post_count": len(
            [item for item in evidence_records if item.get("source_type") == "live_job_post"]
        ),
        "live_public_page_count": len(
            [item for item in evidence_records if item.get("source_type") == "live_public_page"]
        ),
        "local_record_count": len(
            [item for item in evidence_records if str(item.get("source_type", "")).startswith("live_") is False]
        ),
    }
    return ResearchResult(evidence_records=evidence_records, source_summary=source_summary)

from backend.roadmap_engine.services import goal_intelligence_service
from backend.roadmap_engine.services.agent_models import RoleIntentResult


def run(*, goal_text: str, target_duration_months: int) -> RoleIntentResult:
    goal_parse = goal_intelligence_service.parse_goal_text(goal_text)
    role_intent = goal_intelligence_service._build_role_intent(  # noqa: SLF001
        goal_text,
        goal_parse.get("target_company"),
        goal_parse.get("target_role_family"),
        target_duration_months,
    )
    return RoleIntentResult(goal_parse=goal_parse, role_intent=role_intent)

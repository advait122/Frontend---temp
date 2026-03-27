import json
import os

from backend.roadmap_engine.services import goal_intelligence_service
from backend.roadmap_engine.services.agent_models import PlanningResult

GROQ_MODEL = "llama-3.3-70b-versatile"


def _extract_json_object(raw_text: str) -> dict | None:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _llm_plan(
    *,
    goal_text: str,
    role_intent: dict,
    evidence_summary: dict,
    known_skills: list[str],
    draft_requirements: dict,
) -> dict:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return {}

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "You are planning a role-specific learning roadmap from evidence.\n"
            "Return strict JSON only with keys:\n"
            "interpreted_role, core_skills, support_skills, interview_focus, project_focus, rationale.\n"
            "Rules:\n"
            "- core_skills: 4 to 8 items, most important role-defining skills only\n"
            "- support_skills: 2 to 5 items, useful but secondary\n"
            "- interview_focus: 2 to 5 items\n"
            "- project_focus: short array of 1 to 3 practical project directions\n"
            "- avoid vague phrases like code quality, system health, technical execution\n"
            "- infer the role from evidence, do not just echo the goal text\n\n"
            f"Goal text: {goal_text}\n"
            f"Role intent: {json.dumps(role_intent, ensure_ascii=False)}\n"
            f"Known skills: {json.dumps(known_skills, ensure_ascii=False)}\n"
            f"Evidence summary: {json.dumps(evidence_summary, ensure_ascii=False)}\n"
            f"Draft requirements: {json.dumps(draft_requirements, ensure_ascii=False)}\n"
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You produce structured evidence-grounded roadmap plans in strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json_object(response.choices[0].message.content or "")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_llm_skills(role_intent: dict, llm_plan: dict) -> list[str]:
    skills: list[str] = []
    for key in ("core_skills", "support_skills"):
        for item in llm_plan.get(key, []) if isinstance(llm_plan.get(key), list) else []:
            skills.append(str(item).strip())
    return goal_intelligence_service._clean_skill_candidates(skills, role_intent)  # noqa: SLF001


def run(
    *,
    goal_text: str,
    role_intent: dict,
    evidence_summary: dict,
    known_skills: list[str],
) -> PlanningResult:
    draft_requirements = goal_intelligence_service.synthesize_required_skills(
        goal_text=goal_text,
        target_company=role_intent.get("target_company"),
    )
    llm_plan = _llm_plan(
        goal_text=goal_text,
        role_intent=role_intent,
        evidence_summary=evidence_summary,
        known_skills=known_skills,
        draft_requirements=draft_requirements,
    )
    llm_skills = _normalize_llm_skills(role_intent, llm_plan)
    draft_skills = llm_skills or list(draft_requirements.get("required_skills", []))
    validation_result = goal_intelligence_service._validate_required_skills(  # noqa: SLF001
        role_intent=role_intent,
        draft_skills=draft_skills,
        evidence_summary=evidence_summary,
        known_skills=known_skills,
    )
    validation_result["llm_plan"] = llm_plan
    validation_result["planner_mode"] = "llm" if llm_plan else "fallback"
    if llm_plan.get("interpreted_role"):
        validation_result["interpreted_role"] = llm_plan.get("interpreted_role")
    if llm_plan.get("project_focus") and not validation_result.get("project_recommendations"):
        validation_result["project_recommendations"] = [
            str(item) for item in llm_plan.get("project_focus", []) if str(item).strip()
        ]
    return PlanningResult(
        required_skills=list(validation_result.get("required_skills", [])),
        validation_result=validation_result,
        draft_requirements=draft_requirements,
        rationale=str(llm_plan.get("rationale") or draft_requirements.get("rationale", "")),
        llm_plan=llm_plan,
    )

"""
Main service for the enhanced assessment module.

Provides:
  - generate_enhanced_assessment(student_id, goal_skill_id) -> dict
  - generate_coding_assessment(student_id, goal_skill_id, skill_assessment_id) -> dict
  - submit_coding_assessment(student_id, coding_assessment_id, code_submissions) -> dict
"""

from __future__ import annotations

import os
from datetime import timedelta

from backend.enhanced_assessment import coding_repo
from backend.enhanced_assessment.coding_generator import generate_coding_problems
from backend.enhanced_assessment.grader import combined_score, grade_coding
from backend.enhanced_assessment.mcq_generator import generate_enhanced_mcq
from backend.enhanced_assessment.piston_executor import run_against_test_cases
from backend.enhanced_assessment.topic_config import get_skill_config
from backend.roadmap_engine.constants import PASS_PERCENT_FOR_SKILL_TEST
from backend.roadmap_engine.services.skill_normalizer import normalize_skill
from backend.roadmap_engine.storage import (
    assessment_repo,
    goals_repo,
    matching_repo,
    roadmap_repo,
    students_repo,
)
from backend.roadmap_engine.utils import utc_now_iso, utc_today


# ---------------------------------------------------------------------------
# Internal helpers (mirrors logic in assessment_service.py)
# ---------------------------------------------------------------------------

def _insert_revision_tasks(goal_id: int, goal_skill: dict, weak_topics: list[str]) -> int:
    from datetime import timedelta

    if not weak_topics:
        weak_topics = ["Core Concepts"]

    plan = roadmap_repo.get_active_plan(goal_id)
    if not plan:
        return 0

    today = utc_today()
    existing = roadmap_repo.list_tasks(plan["id"], today.isoformat(), None)
    existing_titles = {
        task["title"]
        for task in existing
        if task.get("goal_skill_id") == goal_skill["id"] and task["is_completed"] == 0
    }

    tasks_to_add = []
    for idx, topic in enumerate(weak_topics[:3]):
        title = f"Revision: {goal_skill['skill_name']} - {topic}"
        if title in existing_titles:
            continue
        task_date = (today + timedelta(days=idx + 1)).isoformat()
        tasks_to_add.append(
            {
                "goal_skill_id": goal_skill["id"],
                "task_date": task_date,
                "title": title,
                "description": (
                    f"Revise topic '{topic}' for {goal_skill['skill_name']}, "
                    "practice questions, then retake the skill test."
                ),
                "target_minutes": 45,
            }
        )

    roadmap_repo.append_tasks(plan["id"], tasks_to_add)
    return len(tasks_to_add)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_enhanced_assessment(student_id: int, goal_skill_id: int) -> dict:
    """
    Drop-in replacement for assessment_service.generate_assessment().

    Returns the same dict structure as a skill_assessments row, PLUS:
      - "has_coding_test": bool
      - "coding_assessment_id": int | None
      - "needs_coding_test": bool (from topic_config)
    """
    from backend.roadmap_engine.services import youtube_learning_service
    from backend.roadmap_engine.services.assessment_service import (
        _assessment_deadline_utc,
        _context_aware_fallback_questions,
        _skill_is_ready_for_test,
    )
    from datetime import datetime, timezone

    goal = goals_repo.get_active_goal(student_id)
    if goal is None:
        raise ValueError("Active goal not found.")

    goal_skill = goals_repo.get_goal_skill(goal_skill_id)
    if goal_skill is None or goal_skill["goal_id"] != goal["id"]:
        raise ValueError("Skill not found for current goal.")

    goal_skills = goals_repo.list_goal_skills(goal["id"])
    active_skill = next((item for item in goal_skills if item["status"] != "completed"), None)
    if active_skill is None:
        raise ValueError("All skills are already completed.")
    if active_skill["id"] != goal_skill_id:
        raise ValueError(
            f"Complete and pass {active_skill['skill_name']} before unlocking this skill test."
        )

    selected_playlist = youtube_learning_service.get_selected_playlist(goal["id"], goal_skill_id)
    if selected_playlist is None:
        raise ValueError(
            f"Select one of the top 3 playlists for {goal_skill['skill_name']} before taking the test."
        )

    if goal_skill["status"] == "completed":
        raise ValueError("Skill already completed.")

    if not _skill_is_ready_for_test(goal["id"], goal_skill_id):
        raise ValueError("Complete all roadmap tasks for this skill before taking the test.")

    cfg = get_skill_config(goal_skill["skill_name"])

    # Re-use existing in-progress attempt
    latest = assessment_repo.get_latest_assessment(goal_skill_id)
    if latest:
        if latest.get("submitted_at") is None:
            latest_deadline = _assessment_deadline_utc(latest)
            now_utc = datetime.now(tz=timezone.utc)
            if latest_deadline is None or now_utc <= (latest_deadline + timedelta(seconds=90)):
                latest["needs_coding_test"] = cfg["needs_coding_test"]
                latest["has_coding_test"] = False
                latest["coding_assessment_id"] = None
                return latest
        if latest.get("passed") == 1:
            latest["needs_coding_test"] = cfg["needs_coding_test"]
            # Check if coding assessment already exists
            ca = coding_repo.get_coding_assessment_by_mcq_id(latest["id"])
            latest["has_coding_test"] = ca is not None
            latest["coding_assessment_id"] = ca["id"] if ca else None
            return latest

    # Generate enhanced MCQ questions
    try:
        questions, answer_key = generate_enhanced_mcq(goal_skill["skill_name"], selected_playlist)
    except Exception:
        questions, answer_key = _context_aware_fallback_questions(
            goal_skill["skill_name"], selected_playlist
        )

    assessment_id = assessment_repo.create_assessment(
        goal_id=goal["id"],
        goal_skill_id=goal_skill_id,
        questions=questions,
        answer_key=answer_key,
    )
    assessment = assessment_repo.get_assessment(assessment_id)
    if assessment is None:
        raise ValueError("Failed to create assessment.")

    assessment["needs_coding_test"] = cfg["needs_coding_test"]
    assessment["has_coding_test"] = False
    assessment["coding_assessment_id"] = None
    return assessment


def generate_coding_assessment(
    student_id: int,
    goal_skill_id: int,
    skill_assessment_id: int,
) -> dict:
    """
    Create (or retrieve) the coding assessment linked to an MCQ assessment.

    Returns the coding assessment dict.
    """
    goal = goals_repo.get_active_goal(student_id)
    if goal is None:
        raise ValueError("Active goal not found.")

    goal_skill = goals_repo.get_goal_skill(goal_skill_id)
    if goal_skill is None or goal_skill["goal_id"] != goal["id"]:
        raise ValueError("Skill not found for current goal.")

    # Don't create if skill already fully completed
    if goal_skill["status"] == "completed":
        raise ValueError("Skill already completed. No coding test needed.")

    # Check if a coding assessment already exists for this MCQ attempt
    existing = coding_repo.get_coding_assessment_by_mcq_id(skill_assessment_id)
    if existing:
        return existing

    cfg = get_skill_config(goal_skill["skill_name"])
    if not cfg["needs_coding_test"]:
        raise ValueError(f"Skill '{goal_skill['skill_name']}' does not require a coding test.")

    # Verify the linked MCQ assessment passed
    mcq_assessment = assessment_repo.get_assessment(skill_assessment_id)
    if mcq_assessment is None:
        raise ValueError("MCQ assessment not found.")
    if mcq_assessment.get("passed") != 1:
        raise ValueError("You must pass the MCQ test before taking the coding test.")

    problems = generate_coding_problems(goal_skill["skill_name"], cfg["language"])
    coding_id = coding_repo.create_coding_assessment(
        skill_assessment_id=skill_assessment_id,
        goal_id=goal["id"],
        goal_skill_id=goal_skill_id,
        questions=problems,
    )
    ca = coding_repo.get_coding_assessment(coding_id)
    if ca is None:
        raise ValueError("Failed to create coding assessment.")
    return ca


def submit_coding_assessment(
    student_id: int,
    coding_assessment_id: int,
    code_submissions: list[str],
) -> dict:
    """
    Execute student code against test cases, grade, and update skill status.

    code_submissions: list of code strings, one per coding question (in order).

    Returns the updated coding assessment dict.
    """
    goal = goals_repo.get_active_goal(student_id)
    if goal is None:
        raise ValueError("Active goal not found.")

    ca = coding_repo.get_coding_assessment(coding_assessment_id)
    if ca is None:
        raise ValueError("Coding assessment not found.")
    if ca["goal_id"] != goal["id"]:
        raise ValueError("Coding assessment does not belong to your current goal.")
    if ca.get("submitted_at"):
        return ca

    questions = ca["questions"]
    cfg = get_skill_config("")
    # Determine language from the first problem (all should share the same language)
    language = "python"
    if questions:
        language = questions[0].get("language", "python")

    # Execute each submission
    execution_results: list[dict] = []
    for idx, problem in enumerate(questions):
        code = code_submissions[idx] if idx < len(code_submissions) else ""
        test_cases = problem.get("test_cases", [])
        tc_results = run_against_test_cases(language, code, test_cases) if code.strip() else [
            {
                "input": tc.get("input", ""),
                "expected_output": tc.get("expected_output", ""),
                "actual_output": "",
                "passed": False,
                "error": "No code submitted",
            }
            for tc in test_cases
        ]
        execution_results.append(
            {
                "problem_title": problem.get("title", f"Problem {idx + 1}"),
                "test_case_results": tc_results,
            }
        )

    coding_grade = grade_coding(execution_results)
    coding_score = coding_grade["score_percent"]

    # Retrieve linked MCQ score
    mcq_assessment = assessment_repo.get_assessment(ca["skill_assessment_id"])
    mcq_score = float(mcq_assessment["score_percent"] or 0.0) if mcq_assessment else 0.0

    final, passed = combined_score(mcq_score, coding_score)

    coding_repo.submit_coding_assessment(
        coding_assessment_id=coding_assessment_id,
        student_submissions=code_submissions,
        execution_results=execution_results,
        score_percent=coding_score,
        passed=passed,
    )

    goal_skill = goals_repo.get_goal_skill(ca["goal_skill_id"])

    if passed:
        if goal_skill:
            completed_at = utc_now_iso()
            goals_repo.set_goal_skill_status(goal_skill["id"], "completed", completed_at)
            students_repo.add_student_skill(
                student_id=student_id,
                skill_name=goal_skill["skill_name"],
                normalized_skill=normalize_skill(goal_skill["skill_name"]),
                skill_source="roadmap_mastered",
            )
            matching_repo.create_notification(
                student_id=student_id,
                goal_id=goal["id"],
                notification_type="skill_test_passed",
                title="Skill Test Passed (Coding)",
                body=(
                    f"You passed {goal_skill['skill_name']} with a combined score of "
                    f"{final:.1f}% (MCQ {mcq_score:.1f}% + Coding {coding_score:.1f}%). "
                    "Skill marked as completed."
                ),
            )
    else:
        if goal_skill:
            goals_repo.set_goal_skill_status(ca["goal_skill_id"], "in_progress", None)
            weak_topics = ["Coding Practice", goal_skill["skill_name"]]
            added = _insert_revision_tasks(goal["id"], goal_skill, weak_topics)
            matching_repo.create_notification(
                student_id=student_id,
                goal_id=goal["id"],
                notification_type="skill_test_failed",
                title="Coding Test Failed",
                body=(
                    f"Combined score {final:.1f}% (MCQ {mcq_score:.1f}% + Coding "
                    f"{coding_score:.1f}%). Need 70% to pass. "
                    f"{added} revision task(s) added."
                ),
            )

    updated = coding_repo.get_coding_assessment(coding_assessment_id)
    if updated is None:
        raise ValueError("Failed to reload coding assessment.")

    # Attach summary fields for templates
    updated["mcq_score"] = mcq_score
    updated["coding_score"] = coding_score
    updated["final_score"] = final
    updated["passed_overall"] = passed
    updated["coding_grade"] = coding_grade
    return updated

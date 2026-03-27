"""
Grading functions for MCQ and coding assessments, and combined score logic.
"""

from __future__ import annotations

from collections import defaultdict


def grade_mcq(
    questions: list[dict],
    answer_key: list[int],
    student_answers: list[int],
) -> dict:
    """
    Grade an MCQ assessment.

    Returns:
        {
            "score_percent": float,
            "correct_count": int,
            "total_count": int,
            "topic_stats": {topic: {"correct": int, "total": int}},
            "weak_topics": list[str],
            "strong_topics": list[str],
        }
    """
    total = len(answer_key)
    correct = 0
    topic_stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})

    for idx, expected in enumerate(answer_key):
        topic = "General"
        if idx < len(questions):
            topic = str(questions[idx].get("topic", "General")).strip() or "General"
        topic_stats[topic]["total"] += 1
        if idx < len(student_answers) and student_answers[idx] == expected:
            correct += 1
            topic_stats[topic]["correct"] += 1

    score_percent = (correct / total * 100) if total else 0.0

    weak_topics: list[str] = []
    strong_topics: list[str] = []
    for topic, stats in topic_stats.items():
        t = max(stats["total"], 1)
        ratio = stats["correct"] / t
        if ratio < 0.5:
            weak_topics.append(topic)
        elif ratio >= 0.8:
            strong_topics.append(topic)

    return {
        "score_percent": round(score_percent, 2),
        "correct_count": correct,
        "total_count": total,
        "topic_stats": dict(topic_stats),
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
    }


def grade_coding(execution_results: list[dict]) -> dict:
    """
    Grade a coding assessment from per-question execution results.

    execution_results: list of per-question dicts, each containing a
        "test_case_results" key with a list of test-case result dicts
        ({"passed": bool, ...}).

    Returns:
        {
            "score_percent": float,
            "questions_passed": int,
            "total_questions": int,
        }
    """
    total_questions = len(execution_results)
    if total_questions == 0:
        return {
            "score_percent": 0.0,
            "questions_passed": 0,
            "total_questions": 0,
        }

    questions_passed = 0
    for q_result in execution_results:
        tc_results = q_result.get("test_case_results", [])
        if not tc_results:
            continue
        all_passed = all(tc.get("passed", False) for tc in tc_results)
        if all_passed:
            questions_passed += 1

    score_percent = (questions_passed / total_questions * 100) if total_questions else 0.0
    return {
        "score_percent": round(score_percent, 2),
        "questions_passed": questions_passed,
        "total_questions": total_questions,
    }


def combined_score(
    mcq_score: float,
    coding_score: float | None,
) -> tuple[float, bool]:
    """
    Calculate the combined final score.

    - If coding_score is provided: final = (mcq_score + coding_score) / 2
    - Otherwise: final = mcq_score
    - Pass threshold: 70%

    Returns (final_score_percent, passed).
    """
    if coding_score is None:
        final = mcq_score
    else:
        final = (mcq_score + coding_score) / 2.0

    return round(final, 2), final >= 70.0

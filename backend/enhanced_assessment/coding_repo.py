"""
Database operations for the coding_assessments table.
"""

from __future__ import annotations

import json

from backend.roadmap_engine.storage.database import get_connection, transaction
from backend.roadmap_engine.utils import utc_now_iso


def _get_attempt_count(goal_skill_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM coding_assessments WHERE goal_skill_id = ?",
            (goal_skill_id,),
        ).fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def create_coding_assessment(
    *,
    skill_assessment_id: int,
    goal_id: int,
    goal_skill_id: int,
    questions: list[dict],
) -> int:
    """
    Insert a new coding assessment record and return its id.
    """
    now = utc_now_iso()
    attempt_no = _get_attempt_count(goal_skill_id) + 1

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO coding_assessments (
                skill_assessment_id,
                goal_id,
                goal_skill_id,
                attempt_no,
                questions_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                skill_assessment_id,
                goal_id,
                goal_skill_id,
                attempt_no,
                json.dumps(questions, ensure_ascii=False),
                now,
            ),
        )
        return int(cursor.lastrowid)


def get_coding_assessment_by_mcq_id(skill_assessment_id: int) -> dict | None:
    """Return the coding assessment linked to the given MCQ skill_assessment_id, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM coding_assessments
            WHERE skill_assessment_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (skill_assessment_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return _deserialise(dict(row))


def get_coding_assessment(coding_assessment_id: int) -> dict | None:
    """Return the coding assessment with the given id, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM coding_assessments WHERE id = ?",
            (coding_assessment_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return _deserialise(dict(row))


def submit_coding_assessment(
    *,
    coding_assessment_id: int,
    student_submissions: list[str],
    execution_results: list[dict],
    score_percent: float,
    passed: bool,
) -> None:
    """Persist submission results for a coding assessment."""
    now = utc_now_iso()
    with transaction() as conn:
        conn.execute(
            """
            UPDATE coding_assessments
            SET
                student_submissions_json = ?,
                execution_results_json = ?,
                score_percent = ?,
                passed = ?,
                submitted_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(student_submissions, ensure_ascii=False),
                json.dumps(execution_results, ensure_ascii=False),
                score_percent,
                1 if passed else 0,
                now,
                coding_assessment_id,
            ),
        )


def _deserialise(row: dict) -> dict:
    """Decode JSON columns in a coding_assessments row."""
    row["questions"] = json.loads(row.get("questions_json") or "[]")
    raw_subs = row.get("student_submissions_json")
    row["student_submissions"] = json.loads(raw_subs) if raw_subs else []
    raw_exec = row.get("execution_results_json")
    row["execution_results"] = json.loads(raw_exec) if raw_exec else []
    return row

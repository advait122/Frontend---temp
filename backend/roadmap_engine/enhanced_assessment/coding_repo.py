import json

from backend.roadmap_engine.storage.database import get_connection, transaction
from backend.roadmap_engine.utils import utc_now_iso


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS skill_coding_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL UNIQUE,
    goal_id INTEGER NOT NULL,
    goal_skill_id INTEGER NOT NULL,
    coding_questions_json TEXT NOT NULL,
    latest_submission_json TEXT,
    score_percent REAL,
    passed INTEGER,
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    FOREIGN KEY(assessment_id) REFERENCES skill_assessments(id) ON DELETE CASCADE,
    FOREIGN KEY(goal_id) REFERENCES career_goals(id) ON DELETE CASCADE,
    FOREIGN KEY(goal_skill_id) REFERENCES career_goal_skills(id) ON DELETE CASCADE
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_skill_coding_assessments_assessment
ON skill_coding_assessments(assessment_id);
"""


def ensure_table() -> None:
    with transaction() as connection:
        connection.execute(CREATE_TABLE_SQL)
        connection.execute(CREATE_INDEX_SQL)


def create_or_replace_coding_assessment(
    *,
    assessment_id: int,
    goal_id: int,
    goal_skill_id: int,
    questions: list[dict],
) -> None:
    ensure_table()
    now = utc_now_iso()
    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO skill_coding_assessments (
                assessment_id,
                goal_id,
                goal_skill_id,
                coding_questions_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(assessment_id) DO UPDATE SET
                coding_questions_json = excluded.coding_questions_json,
                created_at = excluded.created_at,
                latest_submission_json = NULL,
                score_percent = NULL,
                passed = NULL,
                submitted_at = NULL
            """,
            (
                assessment_id,
                goal_id,
                goal_skill_id,
                json.dumps(questions, ensure_ascii=False),
                now,
            ),
        )


def get_coding_assessment(assessment_id: int) -> dict | None:
    ensure_table()
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT
                id,
                assessment_id,
                goal_id,
                goal_skill_id,
                coding_questions_json,
                latest_submission_json,
                score_percent,
                passed,
                created_at,
                submitted_at
            FROM skill_coding_assessments
            WHERE assessment_id = ?
            """,
            (assessment_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    item = dict(row)
    item["questions"] = json.loads(item["coding_questions_json"]) if item["coding_questions_json"] else []
    item["latest_submission"] = (
        json.loads(item["latest_submission_json"]) if item["latest_submission_json"] else None
    )
    return item


def submit_coding_assessment(
    *,
    assessment_id: int,
    latest_submission: dict,
    score_percent: float,
    passed: bool,
) -> None:
    ensure_table()
    now = utc_now_iso()
    with transaction() as connection:
        connection.execute(
            """
            UPDATE skill_coding_assessments
            SET
                latest_submission_json = ?,
                score_percent = ?,
                passed = ?,
                submitted_at = ?
            WHERE assessment_id = ?
            """,
            (
                json.dumps(latest_submission, ensure_ascii=False),
                float(score_percent),
                1 if passed else 0,
                now,
                assessment_id,
            ),
        )

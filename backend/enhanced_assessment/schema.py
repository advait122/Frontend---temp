"""
Schema for the coding_assessments table used by the enhanced assessment module.
Call init_enhanced_schema() at app startup.
"""

from backend.roadmap_engine.storage.database import transaction


def init_enhanced_schema() -> None:
    """Create the coding_assessments table if it does not already exist."""
    with transaction() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS coding_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_assessment_id INTEGER NOT NULL,
                goal_id INTEGER NOT NULL,
                goal_skill_id INTEGER NOT NULL,
                attempt_no INTEGER NOT NULL DEFAULT 1,
                questions_json TEXT NOT NULL,
                student_submissions_json TEXT,
                execution_results_json TEXT,
                score_percent REAL,
                passed INTEGER,
                created_at TEXT NOT NULL,
                submitted_at TEXT,
                FOREIGN KEY(skill_assessment_id) REFERENCES skill_assessments(id) ON DELETE CASCADE
            )
            """
        )

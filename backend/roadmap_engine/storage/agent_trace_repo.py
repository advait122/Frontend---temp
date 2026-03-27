import json

from backend.roadmap_engine.storage.database import transaction
from backend.roadmap_engine.utils import utc_now_iso


def create_agent_run(
    *,
    student_id: int | None,
    goal_text: str,
    status: str,
    trace: dict,
) -> int:
    now = utc_now_iso()
    trace_json = json.dumps(trace, ensure_ascii=False)

    with transaction() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO roadmap_agent_runs (
                student_id,
                goal_text,
                status,
                trace_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, goal_text, status, trace_json, now, now),
        )
        return int(cursor.lastrowid)

import json
from datetime import datetime, timedelta, timezone

from backend.roadmap_engine.storage.database import get_connection, transaction
from backend.roadmap_engine.utils import utc_now_iso


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_fresh_cache(role_cache_key: str, max_age_hours: int) -> dict | None:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT
                role_cache_key,
                role_family,
                target_company,
                evidence_json,
                source_summary_json,
                created_at,
                updated_at
            FROM roadmap_evidence_cache
            WHERE role_cache_key = ?
            LIMIT 1
            """,
            (role_cache_key,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    cache = dict(row)
    updated_at = _parse_iso(cache.get("updated_at"))
    if updated_at is None:
        return None

    age_limit = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    if updated_at < age_limit:
        return None

    try:
        cache["evidence"] = json.loads(cache.get("evidence_json") or "[]")
    except json.JSONDecodeError:
        cache["evidence"] = []

    try:
        cache["source_summary"] = json.loads(cache.get("source_summary_json") or "{}")
    except json.JSONDecodeError:
        cache["source_summary"] = {}

    return cache


def upsert_cache(
    *,
    role_cache_key: str,
    role_family: str,
    target_company: str | None,
    evidence: list[dict],
    source_summary: dict,
) -> None:
    now = utc_now_iso()
    evidence_json = json.dumps(evidence, ensure_ascii=False)
    source_summary_json = json.dumps(source_summary, ensure_ascii=False)

    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO roadmap_evidence_cache (
                role_cache_key,
                role_family,
                target_company,
                evidence_json,
                source_summary_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role_cache_key) DO UPDATE SET
                role_family = excluded.role_family,
                target_company = excluded.target_company,
                evidence_json = excluded.evidence_json,
                source_summary_json = excluded.source_summary_json,
                updated_at = excluded.updated_at
            """,
            (
                role_cache_key,
                role_family,
                target_company,
                evidence_json,
                source_summary_json,
                now,
                now,
            ),
        )

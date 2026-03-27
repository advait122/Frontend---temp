import json
import os
from pathlib import Path


def crawler_knowledge_for_skill(skill_name: str, max_items: int = 12) -> list[dict]:
    path = _knowledge_path()
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    if not isinstance(sources, list):
        return []

    skill_key = skill_name.lower().strip()
    results: list[dict] = []
    for source in sources:
        source_name = str(source.get("source_name", "")).strip()
        items = source.get("items", [])
        if not isinstance(items, list):
            continue

        for item in items:
            if len(results) >= max_items:
                return results
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            text = " ".join(
                [
                    str(item.get("content_type", "")),
                    str(item.get("url", "")),
                    str(item.get("html", ""))[:5000],
                ]
            ).lower()
            if skill_key and skill_key not in text:
                continue
            results.append(
                {
                    "source_name": source_name,
                    "url": url,
                }
            )
    return results


def _knowledge_path() -> Path:
    raw = os.getenv(
        "ENHANCED_ASSESSMENT_CRAWLER_JSON",
        "backend/web_data_engine/crawler_v2/latest_crawl.json",
    )
    return Path(raw)


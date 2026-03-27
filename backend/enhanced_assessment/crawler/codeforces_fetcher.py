"""
Fetches problems from the Codeforces public API filtered by skill-relevant tags.
Maps ratings to difficulty tiers and returns up to 5 problems per tier.
"""

from __future__ import annotations

import requests

CF_API_URL = "https://codeforces.com/api/problemset.problems"

# Rating bands → difficulty labels
RATING_TO_DIFFICULTY = [
    (800, 1200, "easy"),
    (1300, 1800, "medium"),
    (1900, 9999, "hard"),
]


def fetch_problems(codeforces_tags: list[str], max_per_tier: int = 5) -> list[dict]:
    """
    Fetch Codeforces problems matching any of the provided tags.

    Returns a list of dicts:
        {"name": str, "tags": list[str], "difficulty": str, "rating": int}

    Returns an empty list on any error.
    """
    if not codeforces_tags:
        return []

    try:
        resp = requests.get(CF_API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    if data.get("status") != "OK":
        return []

    problems = data.get("result", {}).get("problems", [])
    tag_set = {t.lower() for t in codeforces_tags}

    buckets: dict[str, list[dict]] = {"easy": [], "medium": [], "hard": []}

    for prob in problems:
        prob_tags = [t.lower() for t in (prob.get("tags") or [])]
        if not any(t in tag_set for t in prob_tags):
            continue

        rating = prob.get("rating")
        if not isinstance(rating, int):
            continue

        difficulty = None
        for lo, hi, label in RATING_TO_DIFFICULTY:
            if lo <= rating <= hi:
                difficulty = label
                break
        if difficulty is None:
            continue

        if len(buckets[difficulty]) >= max_per_tier:
            continue

        buckets[difficulty].append(
            {
                "name": prob.get("name", ""),
                "tags": prob_tags,
                "difficulty": difficulty,
                "rating": rating,
            }
        )

        # Stop early once all buckets are filled
        if all(len(v) >= max_per_tier for v in buckets.values()):
            break

    result: list[dict] = []
    for label in ("easy", "medium", "hard"):
        result.extend(buckets[label])
    return result

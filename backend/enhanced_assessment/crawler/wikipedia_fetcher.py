"""
Fetches page summaries from the Wikipedia REST API for a list of search terms.
"""

from __future__ import annotations

import urllib.parse

import requests

WIKI_API_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def fetch_summaries(wikipedia_terms: list[str]) -> list[dict]:
    """
    Fetch Wikipedia page summaries for each term.

    Returns a list of dicts:
        {"title": str, "extract": str}

    Skips any term that fails (network error, 404, etc.).
    """
    results: list[dict] = []

    for term in wikipedia_terms:
        encoded = urllib.parse.quote(term, safe="")
        url = WIKI_API_BASE + encoded
        try:
            resp = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "PathForge-EnhancedAssessment/1.0"},
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            title = data.get("title", term)
            extract = (data.get("extract") or "").strip()
            if extract:
                results.append({"title": title, "extract": extract})
        except Exception:
            continue

    return results

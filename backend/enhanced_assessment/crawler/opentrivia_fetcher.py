"""
Fetches multiple-choice questions from the Open Trivia Database API.
Category 18 = Science: Computers.
"""

from __future__ import annotations

import html

import requests

OPENTRIVIA_URL = "https://opentdb.com/api.php"


def fetch_trivia_questions(amount: int = 10) -> list[dict]:
    """
    Fetch computer-science MCQ questions from Open Trivia DB.

    Returns a list of dicts:
        {
            "question": str,
            "correct_answer": str,
            "incorrect_answers": list[str],
            "difficulty": str,   # "easy" | "medium" | "hard"
        }

    Returns an empty list on any error.
    """
    try:
        resp = requests.get(
            OPENTRIVIA_URL,
            params={"amount": amount, "category": 18, "type": "multiple"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    if data.get("response_code") != 0:
        return []

    results: list[dict] = []
    for item in data.get("results", []):
        question = html.unescape(item.get("question", "")).strip()
        correct = html.unescape(item.get("correct_answer", "")).strip()
        incorrect = [html.unescape(a).strip() for a in (item.get("incorrect_answers") or [])]
        difficulty = str(item.get("difficulty", "medium")).strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        if question and correct:
            results.append(
                {
                    "question": question,
                    "correct_answer": correct,
                    "incorrect_answers": incorrect,
                    "difficulty": difficulty,
                }
            )
    return results

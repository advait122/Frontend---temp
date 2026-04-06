import json
import os
from collections import Counter

from backend.roadmap_engine.enhanced_assessment.coding_languages import (
    default_supported_languages_for_skill,
    normalize_coding_language,
)
from backend.roadmap_engine.enhanced_assessment.knowledge import crawler_knowledge_for_skill


CODING_EASY_COUNT = 3
CODING_MEDIUM_COUNT = 5
CODING_HARD_COUNT = 2
CODING_TOTAL_COUNT = CODING_EASY_COUNT + CODING_MEDIUM_COUNT + CODING_HARD_COUNT
GROQ_MODEL = "llama-3.1-8b-instant"


def build_coding_assessment(skill_name: str, selected_playlist: dict | None) -> dict:
    generated = _llm_coding(skill_name, selected_playlist or {})
    if generated:
        return generated
    return {
        "required": True,
        "questions": _fallback_coding_questions(skill_name),
    }


def _llm_coding(skill_name: str, selected_playlist: dict) -> dict | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    summary = selected_playlist.get("summary", {}) if isinstance(selected_playlist, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    knowledge_items = crawler_knowledge_for_skill(skill_name, max_items=16)
    knowledge_text = "\n".join([f"- {item['source_name']}: {item['url']}" for item in knowledge_items])

    allowed_languages = default_supported_languages_for_skill(skill_name)
    allowed_languages_json = json.dumps(allowed_languages)
    prompt = (
        f"Create exactly {CODING_TOTAL_COUNT} coding questions for {skill_name}.\n"
        "Difficulty mix must be exact:\n"
        f"- easy: {CODING_EASY_COUNT}\n"
        f"- medium: {CODING_MEDIUM_COUNT}\n"
        f"- hard: {CODING_HARD_COUNT}\n"
        "Return strict JSON only:\n"
        "{ \"questions\": ["
        "{ \"question_id\": str, \"difficulty\": \"easy\"|\"medium\"|\"hard\", \"title\": str, "
        "\"statement\": str, \"input_format\": str, \"output_format\": str, "
        "\"sample_input\": str, \"sample_output\": str, "
        "\"test_cases\": [{\"input\": str, \"expected_output\": str, \"is_sample\": bool}], "
        f"\"supported_languages\": {allowed_languages_json} }} ] }}\n"
        "Every question must include at least 3 test cases; at least 1 sample case.\n"
        "Keep stdin/stdout style only.\n\n"
        f"Playlist title: {selected_playlist.get('title', '')}\n"
        f"Topics covered: {summary.get('topics_covered_summary', '')}\n"
        f"Crawler references:\n{knowledge_text if knowledge_text else '- None provided'}\n"
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You create coding assessments in strict JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json(response.choices[0].message.content or "")
        if not parsed:
            return None
        normalized = _normalize_questions(parsed.get("questions"), skill_name)
        if len(normalized) != CODING_TOTAL_COUNT:
            return None
        counts = Counter([q["difficulty"] for q in normalized])
        if (
            counts.get("easy", 0) != CODING_EASY_COUNT
            or counts.get("medium", 0) != CODING_MEDIUM_COUNT
            or counts.get("hard", 0) != CODING_HARD_COUNT
        ):
            return None
        return {"required": True, "questions": normalized}
    except Exception:
        return None


def _extract_json(raw_text: str) -> dict | None:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _normalize_difficulty(value: str) -> str:
    key = str(value or "").strip().lower()
    if key in {"easy", "basic"}:
        return "easy"
    if key in {"hard", "advanced"}:
        return "hard"
    return "medium"


def _normalize_questions(raw: object, skill_name: str) -> list[dict]:
    if not isinstance(raw, list):
        return []
    default_languages = default_supported_languages_for_skill(skill_name)
    output: list[dict] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        statement = str(item.get("statement", "")).strip()
        if not title or not statement:
            continue
        difficulty = _normalize_difficulty(item.get("difficulty"))
        test_cases_raw = item.get("test_cases", [])
        if not isinstance(test_cases_raw, list):
            continue
        test_cases: list[dict] = []
        for case in test_cases_raw:
            if not isinstance(case, dict):
                continue
            inp = str(case.get("input", ""))
            out = str(case.get("expected_output", ""))
            if not inp and out == "":
                continue
            test_cases.append(
                {
                    "input": inp,
                    "expected_output": out,
                    "is_sample": bool(case.get("is_sample", False)),
                }
            )
        if len(test_cases) < 3:
            continue
        if not any(case.get("is_sample") for case in test_cases):
            test_cases[0]["is_sample"] = True

        languages = item.get("supported_languages", list(default_languages))
        if not isinstance(languages, list) or not languages:
            languages = list(default_languages)
        supported = []
        for language in languages:
            key = normalize_coding_language(str(language))
            if not key:
                continue
            if key not in supported:
                supported.append(key)
        if not supported:
            supported = list(default_languages)

        output.append(
            {
                "question_id": str(item.get("question_id", f"cq_{idx + 1}")).strip() or f"cq_{idx + 1}",
                "difficulty": difficulty,
                "title": title,
                "statement": statement,
                "input_format": str(item.get("input_format", "")).strip(),
                "output_format": str(item.get("output_format", "")).strip(),
                "sample_input": str(item.get("sample_input", "")).strip(),
                "sample_output": str(item.get("sample_output", "")).strip(),
                "test_cases": test_cases,
                "supported_languages": supported,
            }
        )
    return output[:CODING_TOTAL_COUNT]


def _fallback_coding_questions(skill_name: str) -> list[dict]:
    default_languages = default_supported_languages_for_skill(skill_name)
    titles = [
        ("easy", "Sum Two Integers", "Read two integers and print their sum."),
        ("easy", "Max In Array", "Read n and n integers. Print the maximum value."),
        ("easy", "Palindrome String", "Read a string and print YES if palindrome else NO."),
        ("medium", "Count Distinct", "Read n and n integers. Print number of distinct values."),
        ("medium", "Sort Numbers", "Read n and n integers. Print numbers in ascending order."),
        ("medium", "Nth Fibonacci", "Read n (0-indexed). Print nth Fibonacci number."),
        ("medium", "Valid Anagram", "Read two strings and print YES if they are anagrams else NO."),
        ("medium", "Frequency Map", "Read n and n integers. Print value:count sorted by value."),
        ("hard", "Maximum Subarray Sum", "Read n and n integers. Print maximum subarray sum."),
        ("hard", "Longest Increasing Subsequence Length", "Read n and n integers. Print LIS length."),
    ]

    cases = [
        [
            {"input": "2 3\n", "expected_output": "5", "is_sample": True},
            {"input": "-2 9\n", "expected_output": "7", "is_sample": False},
            {"input": "100 250\n", "expected_output": "350", "is_sample": False},
        ],
        [
            {"input": "5\n1 9 3 7 2\n", "expected_output": "9", "is_sample": True},
            {"input": "4\n-10 -1 -7 -3\n", "expected_output": "-1", "is_sample": False},
            {"input": "1\n42\n", "expected_output": "42", "is_sample": False},
        ],
        [
            {"input": "level\n", "expected_output": "YES", "is_sample": True},
            {"input": "roadmap\n", "expected_output": "NO", "is_sample": False},
            {"input": "abba\n", "expected_output": "YES", "is_sample": False},
        ],
        [
            {"input": "5\n1 2 2 3 3\n", "expected_output": "3", "is_sample": True},
            {"input": "4\n9 9 9 9\n", "expected_output": "1", "is_sample": False},
            {"input": "6\n1 2 3 4 5 6\n", "expected_output": "6", "is_sample": False},
        ],
        [
            {"input": "5\n5 1 4 2 3\n", "expected_output": "1 2 3 4 5", "is_sample": True},
            {"input": "4\n7 7 3 1\n", "expected_output": "1 3 7 7", "is_sample": False},
            {"input": "1\n8\n", "expected_output": "8", "is_sample": False},
        ],
        [
            {"input": "7\n", "expected_output": "13", "is_sample": True},
            {"input": "0\n", "expected_output": "0", "is_sample": False},
            {"input": "10\n", "expected_output": "55", "is_sample": False},
        ],
        [
            {"input": "listen\nsilent\n", "expected_output": "YES", "is_sample": True},
            {"input": "hello\nworld\n", "expected_output": "NO", "is_sample": False},
            {"input": "triangle\nintegral\n", "expected_output": "YES", "is_sample": False},
        ],
        [
            {"input": "5\n1 1 2 3 3\n", "expected_output": "1:2 2:1 3:2", "is_sample": True},
            {"input": "4\n4 4 4 4\n", "expected_output": "4:4", "is_sample": False},
            {"input": "3\n2 1 2\n", "expected_output": "1:1 2:2", "is_sample": False},
        ],
        [
            {"input": "8\n-2 -3 4 -1 -2 1 5 -3\n", "expected_output": "7", "is_sample": True},
            {"input": "5\n-5 -1 -8 -2 -3\n", "expected_output": "-1", "is_sample": False},
            {"input": "5\n1 2 3 4 5\n", "expected_output": "15", "is_sample": False},
        ],
        [
            {"input": "8\n10 9 2 5 3 7 101 18\n", "expected_output": "4", "is_sample": True},
            {"input": "5\n5 4 3 2 1\n", "expected_output": "1", "is_sample": False},
            {"input": "6\n1 2 3 4 5 6\n", "expected_output": "6", "is_sample": False},
        ],
    ]

    questions: list[dict] = []
    for idx, (difficulty, title, statement) in enumerate(titles):
        questions.append(
            {
                "question_id": f"cq_{idx + 1}",
                "difficulty": difficulty,
                "title": f"{title} ({skill_name})",
                "statement": statement,
                "input_format": "Read from standard input.",
                "output_format": "Write result to standard output.",
                "sample_input": cases[idx][0]["input"].strip("\n"),
                "sample_output": cases[idx][0]["expected_output"],
                "test_cases": cases[idx],
                "supported_languages": list(default_languages),
            }
        )
    return questions


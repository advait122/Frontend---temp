"""
Generates coding assessment problems using the Groq LLM.
Minimum 10 problems: 30% easy (3), 50% medium (5), 20% hard (2).
Each problem includes 5 test cases (2 visible examples + 3 hidden).
Falls back to hardcoded problems on any failure.
"""

from __future__ import annotations

import json
import os

GROQ_MODEL = "llama-3.3-70b-versatile"
CODING_MIN_PROBLEMS = 10


def _extract_json_object(raw: str) -> dict | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


def _validate_problem(item: dict, default_language: str) -> dict | None:
    """Validate and normalise a single coding problem dict."""
    if not isinstance(item, dict):
        return None
    title = str(item.get("title", "")).strip()
    description = str(item.get("description", "")).strip()
    if not title or not description:
        return None

    difficulty = str(item.get("difficulty", "medium")).strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    input_format = str(item.get("input_format", "")).strip()
    output_format = str(item.get("output_format", "")).strip()

    examples = []
    for ex in (item.get("examples") or []):
        if isinstance(ex, dict):
            examples.append(
                {
                    "input": str(ex.get("input", "")).strip(),
                    "output": str(ex.get("output", "")).strip(),
                    "explanation": str(ex.get("explanation", "")).strip(),
                }
            )

    test_cases = []
    for tc in (item.get("test_cases") or []):
        if isinstance(tc, dict):
            inp = str(tc.get("input", "")).strip()
            expected = str(tc.get("expected_output", "")).strip()
            test_cases.append({"input": inp, "expected_output": expected})

    if not test_cases:
        return None

    language = str(item.get("language", default_language)).strip() or default_language
    time_limit = 5
    try:
        time_limit = int(item.get("time_limit_seconds", 5))
    except (TypeError, ValueError):
        pass

    return {
        "title": title,
        "difficulty": difficulty,
        "description": description,
        "input_format": input_format,
        "output_format": output_format,
        "examples": examples[:2],
        "test_cases": test_cases[:5],
        "time_limit_seconds": time_limit,
        "language": language,
    }


def _hardcoded_fallback(skill_name: str, language: str) -> list[dict]:
    """Return a minimal set of 10 simple coding problems for Python."""
    lang = language if language in {"python", "cpp", "java", "js"} else "python"
    problems = [
        # Easy (3)
        {
            "title": "Sum of Two Numbers",
            "difficulty": "easy",
            "description": "Read two integers from stdin and print their sum.",
            "input_format": "Two integers a and b on separate lines.",
            "output_format": "A single integer: a + b.",
            "examples": [
                {"input": "3\n5", "output": "8", "explanation": "3 + 5 = 8"},
            ],
            "test_cases": [
                {"input": "3\n5", "expected_output": "8"},
                {"input": "0\n0", "expected_output": "0"},
                {"input": "-1\n1", "expected_output": "0"},
                {"input": "100\n200", "expected_output": "300"},
                {"input": "-10\n-20", "expected_output": "-30"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Largest of Three",
            "difficulty": "easy",
            "description": "Given three integers, print the largest.",
            "input_format": "Three integers on separate lines.",
            "output_format": "A single integer: the maximum.",
            "examples": [
                {"input": "3\n7\n2", "output": "7", "explanation": "7 is the largest"},
            ],
            "test_cases": [
                {"input": "3\n7\n2", "expected_output": "7"},
                {"input": "1\n1\n1", "expected_output": "1"},
                {"input": "-5\n-3\n-10", "expected_output": "-3"},
                {"input": "0\n0\n1", "expected_output": "1"},
                {"input": "100\n99\n98", "expected_output": "100"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Even or Odd",
            "difficulty": "easy",
            "description": "Read an integer and print 'Even' if it is even, otherwise print 'Odd'.",
            "input_format": "A single integer n.",
            "output_format": "'Even' or 'Odd'.",
            "examples": [
                {"input": "4", "output": "Even", "explanation": "4 is divisible by 2"},
            ],
            "test_cases": [
                {"input": "4", "expected_output": "Even"},
                {"input": "7", "expected_output": "Odd"},
                {"input": "0", "expected_output": "Even"},
                {"input": "-3", "expected_output": "Odd"},
                {"input": "100", "expected_output": "Even"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        # Medium (5)
        {
            "title": "Factorial",
            "difficulty": "medium",
            "description": "Compute and print the factorial of a non-negative integer n.",
            "input_format": "A single non-negative integer n (0 <= n <= 12).",
            "output_format": "A single integer: n!",
            "examples": [
                {"input": "5", "output": "120", "explanation": "5! = 120"},
            ],
            "test_cases": [
                {"input": "5", "expected_output": "120"},
                {"input": "0", "expected_output": "1"},
                {"input": "1", "expected_output": "1"},
                {"input": "10", "expected_output": "3628800"},
                {"input": "12", "expected_output": "479001600"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Reverse a String",
            "difficulty": "medium",
            "description": "Read a string and print it reversed.",
            "input_format": "A single line containing a string.",
            "output_format": "The reversed string.",
            "examples": [
                {"input": "hello", "output": "olleh", "explanation": "Reversed 'hello'"},
            ],
            "test_cases": [
                {"input": "hello", "expected_output": "olleh"},
                {"input": "a", "expected_output": "a"},
                {"input": "abcd", "expected_output": "dcba"},
                {"input": "racecar", "expected_output": "racecar"},
                {"input": "12345", "expected_output": "54321"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Count Vowels",
            "difficulty": "medium",
            "description": "Count the number of vowels (a, e, i, o, u — case insensitive) in a string.",
            "input_format": "A single line containing a string.",
            "output_format": "A single integer: the vowel count.",
            "examples": [
                {"input": "Hello World", "output": "3", "explanation": "e, o, o"},
            ],
            "test_cases": [
                {"input": "Hello World", "expected_output": "3"},
                {"input": "aeiou", "expected_output": "5"},
                {"input": "bcdfg", "expected_output": "0"},
                {"input": "AEIOU", "expected_output": "5"},
                {"input": "", "expected_output": "0"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Fibonacci Sequence",
            "difficulty": "medium",
            "description": "Print the first n numbers of the Fibonacci sequence, space-separated.",
            "input_format": "A single positive integer n.",
            "output_format": "n space-separated integers.",
            "examples": [
                {"input": "7", "output": "0 1 1 2 3 5 8", "explanation": "First 7 Fibonacci numbers"},
            ],
            "test_cases": [
                {"input": "7", "expected_output": "0 1 1 2 3 5 8"},
                {"input": "1", "expected_output": "0"},
                {"input": "2", "expected_output": "0 1"},
                {"input": "5", "expected_output": "0 1 1 2 3"},
                {"input": "10", "expected_output": "0 1 1 2 3 5 8 13 21 34"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Sum of Digits",
            "difficulty": "medium",
            "description": "Read a non-negative integer and print the sum of its digits.",
            "input_format": "A single non-negative integer.",
            "output_format": "A single integer: the digit sum.",
            "examples": [
                {"input": "1234", "output": "10", "explanation": "1+2+3+4=10"},
            ],
            "test_cases": [
                {"input": "1234", "expected_output": "10"},
                {"input": "0", "expected_output": "0"},
                {"input": "9", "expected_output": "9"},
                {"input": "999", "expected_output": "27"},
                {"input": "100", "expected_output": "1"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        # Hard (2)
        {
            "title": "Check Prime",
            "difficulty": "hard",
            "description": (
                "Determine if a given integer n is prime. "
                "Print 'Prime' if it is, otherwise print 'Not Prime'."
            ),
            "input_format": "A single integer n (1 <= n <= 10^6).",
            "output_format": "'Prime' or 'Not Prime'.",
            "examples": [
                {"input": "7", "output": "Prime", "explanation": "7 has no divisors other than 1 and itself"},
            ],
            "test_cases": [
                {"input": "7", "expected_output": "Prime"},
                {"input": "1", "expected_output": "Not Prime"},
                {"input": "2", "expected_output": "Prime"},
                {"input": "4", "expected_output": "Not Prime"},
                {"input": "997", "expected_output": "Prime"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
        {
            "title": "Two Sum",
            "difficulty": "hard",
            "description": (
                "Given an array of integers and a target sum, find the indices of the two numbers "
                "that add up to the target. Print the two 0-based indices separated by a space. "
                "Assume exactly one solution exists."
            ),
            "input_format": (
                "Line 1: space-separated integers (the array).\n"
                "Line 2: the target integer."
            ),
            "output_format": "Two space-separated 0-based indices i j where i < j.",
            "examples": [
                {
                    "input": "2 7 11 15\n9",
                    "output": "0 1",
                    "explanation": "2 + 7 = 9, indices 0 and 1",
                }
            ],
            "test_cases": [
                {"input": "2 7 11 15\n9", "expected_output": "0 1"},
                {"input": "3 2 4\n6", "expected_output": "1 2"},
                {"input": "1 5 3 8\n9", "expected_output": "1 3"},
                {"input": "0 4 3 0\n0", "expected_output": "0 3"},
                {"input": "1 2 3 4 5\n9", "expected_output": "3 4"},
            ],
            "time_limit_seconds": 5,
            "language": lang,
        },
    ]
    return problems


def generate_coding_problems(skill_name: str, language: str) -> list[dict]:
    """
    Generate coding problems for the given skill using the Groq LLM.
    Returns a list of validated problem dicts.
    Falls back to hardcoded problems on failure.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _hardcoded_fallback(skill_name, language)

    prompt = (
        f"Generate exactly {CODING_MIN_PROBLEMS} coding problems for the skill '{skill_name}'. "
        f"The student will solve them in {language}.\n\n"
        "Difficulty distribution (STRICT):\n"
        "  - 3 EASY problems (30%): straightforward input/output, basic logic\n"
        "  - 5 MEDIUM problems (50%): algorithms, data structures, moderate logic\n"
        "  - 2 HARD problems (20%): complex algorithms, optimisation, edge cases\n\n"
        "For EACH problem provide:\n"
        "  - title: concise problem title\n"
        "  - difficulty: 'easy', 'medium', or 'hard'\n"
        "  - description: clear problem statement\n"
        "  - input_format: how input is provided via stdin\n"
        "  - output_format: exact output format\n"
        "  - examples: list of 2 visible examples with input, output, explanation\n"
        "  - test_cases: list of 5 test cases (2 match examples + 3 hidden edge cases)\n"
        "    Each test case: {input: str, expected_output: str}\n"
        "    expected_output must be EXACT (no trailing whitespace except a final newline)\n"
        f"  - language: '{language}'\n"
        "  - time_limit_seconds: 5\n\n"
        "Return ONLY valid JSON (no markdown, no extra text):\n"
        '{"problems": [{ ... }, ...]}\n'
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate technical coding problems with precise test cases. "
                        "Output only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
        parsed = _extract_json_object(raw)
        if not parsed:
            return _hardcoded_fallback(skill_name, language)

        raw_problems = parsed.get("problems", [])
        if not isinstance(raw_problems, list):
            return _hardcoded_fallback(skill_name, language)

        valid = []
        for item in raw_problems:
            p = _validate_problem(item, language)
            if p:
                valid.append(p)

        if len(valid) < CODING_MIN_PROBLEMS:
            return _hardcoded_fallback(skill_name, language)

        return valid[:CODING_MIN_PROBLEMS]

    except Exception:
        return _hardcoded_fallback(skill_name, language)

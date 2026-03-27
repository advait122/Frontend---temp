"""
Executes student code against test cases using the Piston API.
https://emkc.org/api/v2/piston/execute
"""

from __future__ import annotations

import requests

PISTON_URL = "https://emkc.org/api/v2/piston/execute"

PISTON_LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    "python": ("python", "3.10.0"),
    "cpp": ("c++", "10.2.0"),
    "java": ("java", "15.0.2"),
    "js": ("javascript", "18.15.0"),
}


def execute_code(
    language: str,
    code: str,
    stdin: str = "",
    timeout: int = 5,
) -> dict:
    """
    Execute a code string via Piston.

    Returns:
        {
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "error": str | None,
        }
    """
    lang_name, lang_version = PISTON_LANGUAGE_MAP.get(language, ("python", "3.10.0"))
    payload = {
        "language": lang_name,
        "version": lang_version,
        "files": [{"content": code}],
        "stdin": stdin,
        "run_timeout": timeout * 1000,
    }
    try:
        resp = requests.post(PISTON_URL, json=payload, timeout=timeout + 5)
        resp.raise_for_status()
        data = resp.json()
        run = data.get("run", {})
        return {
            "stdout": (run.get("stdout") or "").strip(),
            "stderr": (run.get("stderr") or "").strip(),
            "exit_code": run.get("code", -1),
            "error": None,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": str(exc),
        }


def run_against_test_cases(
    language: str,
    code: str,
    test_cases: list[dict],
) -> list[dict]:
    """
    Run code against a list of test cases.

    test_cases: [{"input": str, "expected_output": str}]

    Returns:
        [
            {
                "input": str,
                "expected_output": str,
                "actual_output": str,
                "passed": bool,
                "error": str | None,
            }
        ]
    """
    results: list[dict] = []
    for tc in test_cases:
        stdin = tc.get("input", "")
        expected = (tc.get("expected_output") or "").strip()
        result = execute_code(language, code, stdin=stdin)
        actual = result["stdout"].strip()
        error_msg = result.get("error") or (
            result["stderr"] if result["exit_code"] != 0 else None
        )
        results.append(
            {
                "input": stdin,
                "expected_output": expected,
                "actual_output": actual,
                "passed": actual == expected,
                "error": error_msg,
            }
        )
    return results

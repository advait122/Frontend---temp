import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from backend.roadmap_engine.enhanced_assessment.coding_languages import normalize_coding_language


DEFAULT_PISTON_URL = "https://emkc.org/api/v2/piston/execute"

LANGUAGE_SPECS = {
    "python": {
        "runtime": "python",
        "versions": ["3.10.0", "3.11.4", "3.11.0", "3.9.4"],
        "filename": "main.py",
    },
    "cpp": {
        "runtime": "cpp",
        "versions": ["10.2.0", "17.0.1", "14.0.0"],
        "filename": "main.cpp",
    },
    "c": {
        "runtime": "c",
        "versions": ["10.2.0", "11.2.0"],
        "filename": "main.c",
    },
    "java": {
        "runtime": "java",
        "versions": ["17.0.1", "15.0.2"],
        "filename": "Main.java",
    },
    "javascript": {
        "runtime": "javascript",
        "versions": ["18.15.0", "20.5.1"],
        "filename": "main.js",
    },
    "typescript": {
        "runtime": "typescript",
        "versions": ["5.0.3", "4.9.5"],
        "filename": "main.ts",
    },
    "go": {
        "runtime": "go",
        "versions": ["1.20.2", "1.19.5"],
        "filename": "main.go",
    },
    "rust": {
        "runtime": "rust",
        "versions": ["1.68.2", "1.67.1"],
        "filename": "main.rs",
    },
}


def run_code(language: str, code: str, stdin: str, timeout_ms: int = 6000) -> dict:
    normalized_language = normalize_coding_language(language)
    if not normalized_language:
        return {
            "ok": False,
            "error": (
                f"Unsupported language: {language}. Supported: python, cpp, c, java, "
                "javascript, typescript, go, rust"
            ),
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "engine": "none",
        }

    spec = LANGUAGE_SPECS[normalized_language]
    endpoint = os.getenv("PISTON_API_URL", DEFAULT_PISTON_URL).strip() or DEFAULT_PISTON_URL

    remote_result = _run_with_piston(
        endpoint=endpoint,
        language=spec["runtime"],
        versions=list(spec["versions"]),
        filename=str(spec["filename"]),
        code=code,
        stdin=stdin,
        timeout_ms=timeout_ms,
    )
    if remote_result.get("ok"):
        return remote_result

    if os.getenv("LOCAL_CODE_EXECUTION_FALLBACK", "1").strip().lower() in {"1", "true", "yes", "on"}:
        local_result = _run_locally(
            language=normalized_language,
            code=code,
            stdin=stdin,
            timeout_ms=timeout_ms,
        )
        if local_result is not None:
            if not local_result.get("ok") and remote_result.get("error"):
                local_result["error"] = f"{remote_result['error']} | local fallback failed: {local_result.get('error', '')}"
            return local_result

    return remote_result


def _run_with_piston(
    *,
    endpoint: str,
    language: str,
    versions: list[str],
    filename: str,
    code: str,
    stdin: str,
    timeout_ms: int,
) -> dict:
    attempts = versions + [""]
    last_error = "Code execution service unavailable."
    timeout_seconds = max(5, int(timeout_ms / 1000) + 3)

    for version in attempts:
        payload = {
            "language": language,
            "files": [{"name": filename, "content": code}],
            "stdin": stdin,
            "run_timeout": timeout_ms,
        }
        if version:
            payload["version"] = version

        try:
            response = requests.post(endpoint, json=payload, timeout=timeout_seconds)
        except requests.RequestException as error:
            return {
                "ok": False,
                "error": f"Execution request failed: {error}",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "engine": "piston",
            }

        if response.status_code != 200:
            body = (response.text or "").strip()[:500]
            version_note = f" version={version}" if version else ""
            last_error = f"Piston returned status {response.status_code}{version_note}. {body}".strip()
            continue

        try:
            data = response.json()
        except Exception:
            last_error = "Invalid JSON response from code execution service."
            continue

        run_obj = data.get("run", {}) if isinstance(data, dict) else {}
        stdout = str(run_obj.get("stdout", ""))
        stderr = str(run_obj.get("stderr", ""))
        code_value = run_obj.get("code")
        return {
            "ok": True,
            "error": "",
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": int(code_value) if isinstance(code_value, int) else None,
            "engine": "piston",
        }

    return {
        "ok": False,
        "error": last_error,
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "engine": "piston",
    }


def _run_locally(*, language: str, code: str, stdin: str, timeout_ms: int) -> dict | None:
    timeout_seconds = max(1, int(timeout_ms / 1000))

    if language == "python":
        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                input=stdin,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": True,
                "error": "",
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds}s.",
                "exit_code": 124,
                "engine": "local-python",
            }
        return {
            "ok": True,
            "error": "",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exit_code": completed.returncode,
            "engine": "local-python",
        }

    if language == "cpp":
        compiler = shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            return None

        with tempfile.TemporaryDirectory(prefix="pathforge_cpp_") as temp_dir:
            source_path = Path(temp_dir) / "main.cpp"
            exe_path = Path(temp_dir) / ("main.exe" if os.name == "nt" else "main.out")
            source_path.write_text(code, encoding="utf-8")

            try:
                compile_proc = subprocess.run(
                    [compiler, str(source_path), "-std=c++17", "-O2", "-o", str(exe_path)],
                    text=True,
                    capture_output=True,
                    timeout=max(5, timeout_seconds + 2),
                )
            except subprocess.TimeoutExpired:
                return {
                    "ok": True,
                    "error": "",
                    "stdout": "",
                    "stderr": "Compilation timed out.",
                    "exit_code": 124,
                    "engine": "local-cpp",
                }

            if compile_proc.returncode != 0:
                return {
                    "ok": True,
                    "error": "",
                    "stdout": "",
                    "stderr": compile_proc.stderr or compile_proc.stdout,
                    "exit_code": compile_proc.returncode,
                    "engine": "local-cpp",
                }

            try:
                run_proc = subprocess.run(
                    [str(exe_path)],
                    input=stdin,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return {
                    "ok": True,
                    "error": "",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds}s.",
                    "exit_code": 124,
                    "engine": "local-cpp",
                }

            return {
                "ok": True,
                "error": "",
                "stdout": run_proc.stdout,
                "stderr": run_proc.stderr,
                "exit_code": run_proc.returncode,
                "engine": "local-cpp",
            }

    return None

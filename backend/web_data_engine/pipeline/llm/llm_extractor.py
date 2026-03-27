import json
import os
import re
import time

from groq import Groq, RateLimitError

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
MAX_INPUT_CHARS = int(os.getenv("WEB_DATA_LLM_MAX_CHARS", "12000"))

_RATE_LIMIT_COOLDOWN_UNTIL = 0.0

SYSTEM_PROMPT = """
You are an information extraction engine.

Extract structured opportunity data from the given text.

Return ONLY valid JSON.

Fields:
- title
- company
- type -> job / internship / hackathon
- deadline -> last date to apply (null if not found)
- skills -> list of required skills (empty list if not found)

Return valid JSON only. No explanations.
"""


def _strip_code_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_retry_seconds(message: str) -> float:
    retry_message = str(message or "")
    match = re.search(r"try again in\s+(\d+)m(\d+(?:\.\d+)?)s", retry_message, flags=re.IGNORECASE)
    if match:
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        return (minutes * 60.0) + seconds

    match = re.search(r"try again in\s+(\d+(?:\.\d+)?)s", retry_message, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))

    # Safe default if provider message format changes.
    return 120.0


def extract_opportunity_with_llm(clean_text: str) -> dict | None:
    global _RATE_LIMIT_COOLDOWN_UNTIL

    if not clean_text:
        return None

    now = time.time()
    if now < _RATE_LIMIT_COOLDOWN_UNTIL:
        remaining = int(_RATE_LIMIT_COOLDOWN_UNTIL - now)
        print(f"Skipping LLM call due to active rate-limit cooldown ({remaining}s remaining).")
        return None

    compact_text = " ".join(clean_text.split())
    if len(compact_text) > MAX_INPUT_CHARS:
        compact_text = compact_text[:MAX_INPUT_CHARS]

    user_prompt = f"""
Extract the opportunity details from the text below.

TEXT:
{compact_text}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except RateLimitError as error:
        raw_message = str(error)
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            raw_message = str(body.get("error", {}).get("message") or raw_message)

        retry_after = _extract_retry_seconds(raw_message)
        _RATE_LIMIT_COOLDOWN_UNTIL = max(_RATE_LIMIT_COOLDOWN_UNTIL, time.time() + retry_after)

        print(
            "Groq rate limit reached. "
            f"Cooling down for ~{int(retry_after)}s and skipping this page."
        )
        return None
    except Exception as error:
        print(f"LLM request failed: {error}")
        return None

    try:
        content = response.choices[0].message.content
    except Exception:
        print("LLM response did not include a message payload.")
        return None

    cleaned_content = _strip_code_fences(content)

    try:
        return json.loads(cleaned_content)
    except json.JSONDecodeError:
        print("Invalid JSON from LLM response.")
        print(cleaned_content[:500])
        return None

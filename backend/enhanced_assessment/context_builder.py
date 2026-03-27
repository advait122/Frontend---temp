"""
Orchestrates Codeforces, Wikipedia, and Open Trivia fetchers to build
a rich context string for the LLM, keeping it under ~3000 tokens.
"""

from __future__ import annotations

from backend.enhanced_assessment.crawler.codeforces_fetcher import fetch_problems
from backend.enhanced_assessment.crawler.opentrivia_fetcher import fetch_trivia_questions
from backend.enhanced_assessment.crawler.wikipedia_fetcher import fetch_summaries
from backend.enhanced_assessment.topic_config import get_skill_config

# Rough character budget: 3000 tokens × ~4 chars/token = 12000 chars
_CHAR_BUDGET = 12_000


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def build_context(skill_name: str) -> str:
    """
    Build and return a formatted string context containing:
    - Wikipedia topic summaries
    - Codeforces problem examples per difficulty
    - Open Trivia sample MCQ questions

    Total length is kept under ~12 000 characters (≈3000 tokens).
    """
    cfg = get_skill_config(skill_name)

    # --- Wikipedia summaries ---
    wiki_summaries = fetch_summaries(cfg["wikipedia_terms"])

    # --- Codeforces problems ---
    cf_problems = fetch_problems(cfg["codeforces_tags"])

    # --- Open Trivia MCQs ---
    trivia_qs = fetch_trivia_questions(amount=10)

    sections: list[str] = []
    budget_remaining = _CHAR_BUDGET

    # 1. Wikipedia
    if wiki_summaries:
        wiki_lines = ["=== Topic Theory (Wikipedia) ==="]
        for item in wiki_summaries:
            entry = f"[{item['title']}]\n{item['extract']}\n"
            # Truncate individual entries to share budget evenly
            per_entry_budget = max(300, budget_remaining // max(len(wiki_summaries), 1))
            entry = _truncate(entry, per_entry_budget)
            wiki_lines.append(entry)
        wiki_block = "\n".join(wiki_lines)
        wiki_block = _truncate(wiki_block, min(6000, budget_remaining))
        sections.append(wiki_block)
        budget_remaining -= len(wiki_block)

    # 2. Codeforces problems
    if cf_problems and budget_remaining > 500:
        cf_lines = ["=== Codeforces Problem Examples ==="]
        for prob in cf_problems:
            line = (
                f"[{prob['difficulty'].upper()}] {prob['name']} "
                f"(rating {prob['rating']}, tags: {', '.join(prob['tags'][:4])})"
            )
            cf_lines.append(line)
        cf_block = _truncate("\n".join(cf_lines), min(2500, budget_remaining))
        sections.append(cf_block)
        budget_remaining -= len(cf_block)

    # 3. Open Trivia questions as MCQ style examples
    if trivia_qs and budget_remaining > 300:
        trivia_lines = ["=== Sample MCQ Questions (Open Trivia DB) ==="]
        for q in trivia_qs[:8]:
            trivia_lines.append(
                f"Q ({q['difficulty']}): {q['question']}\n"
                f"  Correct: {q['correct_answer']}"
            )
        trivia_block = _truncate("\n".join(trivia_lines), min(2000, budget_remaining))
        sections.append(trivia_block)

    if not sections:
        return f"Skill: {skill_name}\nNo external context available."

    return f"Skill: {skill_name}\n\n" + "\n\n".join(sections)

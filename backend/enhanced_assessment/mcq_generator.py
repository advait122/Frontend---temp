"""
Generates enhanced MCQ tests using the Groq LLM with rich external context.
Minimum 20 questions: 20% easy, 50% medium, 30% hard.
Falls back to a basic generic question set on any failure.
"""

from __future__ import annotations

import json
import math
import os

MCQ_MIN_QUESTIONS = 20
GROQ_MODEL = "llama-3.3-70b-versatile"

# Difficulty distribution
_DIST = {"easy": 0.20, "medium": 0.50, "hard": 0.30}


def _extract_json_object(raw: str) -> dict | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


def _validate_questions(questions: list) -> list[dict]:
    """Return only valid question dicts with all required fields."""
    valid = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        answer = item.get("correct_option_index")
        topic = str(item.get("topic", "General")).strip() or "General"
        difficulty = str(item.get("difficulty", "medium")).strip().lower()
        explanation = str(item.get("explanation", "")).strip()

        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        if not question:
            continue
        if not isinstance(options, list) or len(options) != 4:
            continue
        try:
            answer_int = int(answer)
        except (TypeError, ValueError):
            continue
        if answer_int < 0 or answer_int > 3:
            continue

        valid.append(
            {
                "topic": topic,
                "difficulty": difficulty,
                "question": question,
                "options": [str(o) for o in options],
                "correct_option_index": answer_int,
                "explanation": explanation,
            }
        )
    return valid


def _fallback_questions(skill_name: str) -> tuple[list[dict], list[int]]:
    """Generate 20 generic questions when LLM is unavailable."""
    templates = [
        # easy (4)
        {
            "topic": "Fundamentals",
            "difficulty": "easy",
            "question": f"Which of the following best describes {skill_name}?",
            "options": [
                f"A technology/skill used to build software solutions involving {skill_name}.",
                "A hardware-only specification unrelated to software.",
                "A non-technical communication protocol.",
                "A legacy system with no modern applications.",
            ],
            "correct_option_index": 0,
            "explanation": f"{skill_name} is a widely used technology in modern software development.",
        },
        {
            "topic": "Core Concepts",
            "difficulty": "easy",
            "question": f"What is the primary goal when learning {skill_name}?",
            "options": [
                "To understand core concepts and apply them to real problems.",
                "To memorize syntax without understanding purpose.",
                "To avoid practical exercises and focus only on theory.",
                "To skip fundamentals and learn only advanced topics.",
            ],
            "correct_option_index": 0,
            "explanation": "Understanding core concepts enables practical problem-solving.",
        },
        {
            "topic": "Use Cases",
            "difficulty": "easy",
            "question": f"In which scenario is {skill_name} most commonly applied?",
            "options": [
                "Solving real-world software engineering and development challenges.",
                "Replacing physical hardware components.",
                "Only in non-technical administrative tasks.",
                "Exclusively in academic research with no industry relevance.",
            ],
            "correct_option_index": 0,
            "explanation": f"{skill_name} is applied in diverse real-world software scenarios.",
        },
        {
            "topic": "Learning Path",
            "difficulty": "easy",
            "question": f"What is the recommended starting point for {skill_name}?",
            "options": [
                "Foundational concepts, then hands-on small projects.",
                "Start with the most advanced topic immediately.",
                "Skip all tutorials and jump to production code.",
                "Memorize interview answers before understanding concepts.",
            ],
            "correct_option_index": 0,
            "explanation": "A structured foundational start leads to deeper understanding.",
        },
        # medium (10)
        {
            "topic": "Application",
            "difficulty": "medium",
            "question": f"A developer uses {skill_name} to solve a problem but gets unexpected results. What is the best first step?",
            "options": [
                "Debug by isolating the issue and checking assumptions about inputs.",
                "Rewrite the entire solution from scratch.",
                "Ignore the unexpected results and submit anyway.",
                "Switch to a completely different technology.",
            ],
            "correct_option_index": 0,
            "explanation": "Systematic debugging by isolating components is the correct approach.",
        },
        {
            "topic": "Best Practices",
            "difficulty": "medium",
            "question": f"Which practice leads to maintainable code when using {skill_name}?",
            "options": [
                "Writing modular, well-named, and documented code.",
                "Putting all logic in a single large function.",
                "Avoiding comments to keep code concise.",
                "Using opaque variable names to reduce file size.",
            ],
            "correct_option_index": 0,
            "explanation": "Modularity and documentation are cornerstones of maintainable code.",
        },
        {
            "topic": "Problem Solving",
            "difficulty": "medium",
            "question": f"When optimising a solution built with {skill_name}, which approach should come first?",
            "options": [
                "Profile to identify the actual bottleneck before optimising.",
                "Rewrite everything in assembly language.",
                "Optimise randomly until performance improves.",
                "Remove all abstractions immediately.",
            ],
            "correct_option_index": 0,
            "explanation": "Profiling first ensures effort is spent on actual bottlenecks.",
        },
        {
            "topic": "Error Handling",
            "difficulty": "medium",
            "question": f"How should errors be handled in a {skill_name} application?",
            "options": [
                "Catch specific errors, log them, and provide meaningful messages.",
                "Suppress all errors silently.",
                "Let the application crash and rely on users to report issues.",
                "Use a single catch-all block with no logging.",
            ],
            "correct_option_index": 0,
            "explanation": "Specific error handling with logging improves reliability and debuggability.",
        },
        {
            "topic": "Testing",
            "difficulty": "medium",
            "question": f"What type of testing is most important when developing a {skill_name} component?",
            "options": [
                "Unit tests covering core logic, edge cases, and error paths.",
                "Only manual testing after release.",
                "No testing because the code is straightforward.",
                "Only testing on the production environment.",
            ],
            "correct_option_index": 0,
            "explanation": "Automated unit tests catch regressions early in development.",
        },
        {
            "topic": "Scalability",
            "difficulty": "medium",
            "question": f"Which design choice improves scalability in {skill_name}-based systems?",
            "options": [
                "Designing stateless components and separating concerns.",
                "Coupling all logic tightly into one module.",
                "Avoiding any form of caching.",
                "Using the largest possible data structures always.",
            ],
            "correct_option_index": 0,
            "explanation": "Stateless, decoupled designs scale horizontally more easily.",
        },
        {
            "topic": "Code Review",
            "difficulty": "medium",
            "question": f"During a code review for {skill_name} code, what is the highest-priority concern?",
            "options": [
                "Correctness: does the code do what it is intended to do?",
                "Using the latest trendy libraries regardless of fit.",
                "Minimising code length at the expense of clarity.",
                "Avoiding all use of standard library functions.",
            ],
            "correct_option_index": 0,
            "explanation": "Correctness must be verified before style or other concerns.",
        },
        {
            "topic": "Documentation",
            "difficulty": "medium",
            "question": f"What should documentation for a {skill_name} module include?",
            "options": [
                "Purpose, parameters, return values, and usage examples.",
                "Only the author's name and creation date.",
                "A copy of the entire codebase in plain text.",
                "Nothing — the code is self-explanatory.",
            ],
            "correct_option_index": 0,
            "explanation": "Good documentation covers purpose, API, and usage examples.",
        },
        {
            "topic": "Versioning",
            "difficulty": "medium",
            "question": f"Why is semantic versioning useful for {skill_name} libraries?",
            "options": [
                "It communicates breaking changes, new features, and fixes clearly.",
                "It makes version numbers look more professional.",
                "It prevents users from upgrading dependencies.",
                "It is required by all operating systems.",
            ],
            "correct_option_index": 0,
            "explanation": "Semantic versioning (MAJOR.MINOR.PATCH) signals compatibility intent.",
        },
        {
            "topic": "Security",
            "difficulty": "medium",
            "question": f"Which security practice should always be followed in {skill_name} applications?",
            "options": [
                "Validate and sanitise all user inputs before processing.",
                "Trust all user inputs to improve performance.",
                "Store sensitive data in plain text for simplicity.",
                "Disable authentication for easier testing.",
            ],
            "correct_option_index": 0,
            "explanation": "Input validation is a foundational security measure.",
        },
        # hard (6)
        {
            "topic": "Complexity Analysis",
            "difficulty": "hard",
            "question": f"When evaluating two {skill_name} solutions with the same output, what should determine the preferred choice?",
            "options": [
                "Time and space complexity, maintainability, and edge-case coverage.",
                "Whichever was written first.",
                "The one with more lines of code.",
                "The one that avoids all standard library usage.",
            ],
            "correct_option_index": 0,
            "explanation": "All three dimensions — performance, maintainability, and robustness — matter.",
        },
        {
            "topic": "Edge Cases",
            "difficulty": "hard",
            "question": f"A {skill_name} function works correctly on typical inputs but fails on empty or boundary inputs. What does this reveal?",
            "options": [
                "Insufficient edge-case testing and missing guard clauses.",
                "The function is correctly optimised for the common case.",
                "The testing framework has a bug.",
                "Edge cases do not matter in production.",
            ],
            "correct_option_index": 0,
            "explanation": "Robust code must handle boundary and empty inputs explicitly.",
        },
        {
            "topic": "Design Patterns",
            "difficulty": "hard",
            "question": f"Which design pattern is most appropriate when you need to add behaviour to {skill_name} objects dynamically without modifying their class?",
            "options": [
                "Decorator pattern — wraps objects to extend behaviour at runtime.",
                "Singleton pattern — ensures a single global instance.",
                "Factory pattern — centralises object creation.",
                "Observer pattern — notifies dependents of state changes.",
            ],
            "correct_option_index": 0,
            "explanation": "The Decorator pattern adds responsibilities to objects dynamically.",
        },
        {
            "topic": "Concurrency",
            "difficulty": "hard",
            "question": f"In a concurrent {skill_name} application, a race condition occurs when:",
            "options": [
                "Two threads access shared mutable state without proper synchronisation.",
                "A function executes faster than expected.",
                "Two threads both read immutable data simultaneously.",
                "A single-threaded application uses too much memory.",
            ],
            "correct_option_index": 0,
            "explanation": "Race conditions arise from unsynchronised access to shared mutable state.",
        },
        {
            "topic": "Memory Management",
            "difficulty": "hard",
            "question": f"In the context of {skill_name}, what is the consequence of a memory leak?",
            "options": [
                "Gradual increase in memory usage until the process exhausts available memory.",
                "Immediate program crash on first allocation.",
                "Faster program execution due to cached data.",
                "No observable effect on program behaviour.",
            ],
            "correct_option_index": 0,
            "explanation": "Memory leaks cause progressive memory exhaustion, degrading performance over time.",
        },
        {
            "topic": "System Design",
            "difficulty": "hard",
            "question": f"When designing a large-scale {skill_name}-based system, which principle helps manage growing complexity?",
            "options": [
                "Separation of concerns: divide the system into distinct sections with clear responsibilities.",
                "Monolithic design: keep all functionality in a single module.",
                "Avoid abstractions to minimise indirection.",
                "Duplicate logic freely to avoid cross-module dependencies.",
            ],
            "correct_option_index": 0,
            "explanation": "Separation of concerns reduces coupling and makes large systems manageable.",
        },
    ]

    answer_key = [q["correct_option_index"] for q in templates]
    return templates, answer_key


def generate_mcq(skill_name: str, context: str) -> tuple[list[dict], list[int]]:
    """
    Generate enhanced MCQ questions using the Groq LLM.

    Returns (questions, answer_key) where questions is a list of dicts and
    answer_key is a parallel list of correct option indices (0-3).

    Falls back to _fallback_questions on any failure.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _fallback_questions(skill_name)

    easy_count = math.ceil(MCQ_MIN_QUESTIONS * _DIST["easy"])   # 4
    medium_count = math.ceil(MCQ_MIN_QUESTIONS * _DIST["medium"])  # 10
    hard_count = MCQ_MIN_QUESTIONS - easy_count - medium_count   # 6

    prompt = (
        f"You are an expert technical interviewer. Generate exactly {MCQ_MIN_QUESTIONS} MCQ questions "
        f"to rigorously assess a student's knowledge of '{skill_name}'.\n\n"
        "Use the context below to create relevant, accurate, technically deep questions.\n\n"
        f"Difficulty distribution (STRICT):\n"
        f"  - {easy_count} EASY questions (20%): basic definitions, terminology, simple concepts\n"
        f"  - {medium_count} MEDIUM questions (50%): application, trace code output, pick correct implementation\n"
        f"  - {hard_count} HARD questions (30%): complexity analysis, edge cases, deep system understanding\n\n"
        "Each question MUST have exactly 4 options (index 0-3).\n"
        "Return ONLY valid JSON matching this exact schema (no markdown, no extra text):\n"
        '{"questions": [{"topic": str, "difficulty": "easy"|"medium"|"hard", '
        '"question": str, "options": [str,str,str,str], "correct_option_index": int (0-3), '
        '"explanation": str}]}\n\n'
        "=== CONTEXT ===\n"
        f"{context}\n"
        "=== END CONTEXT ===\n"
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.4,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert technical interviewer creating rigorous MCQ tests. Output only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
        parsed = _extract_json_object(raw)
        if not parsed:
            return _fallback_questions(skill_name)

        raw_questions = parsed.get("questions", [])
        if not isinstance(raw_questions, list):
            return _fallback_questions(skill_name)

        valid = _validate_questions(raw_questions)
        if len(valid) < MCQ_MIN_QUESTIONS:
            return _fallback_questions(skill_name)

        questions = valid[:MCQ_MIN_QUESTIONS]
        answer_key = [q["correct_option_index"] for q in questions]
        return questions, answer_key

    except Exception:
        return _fallback_questions(skill_name)


def generate_enhanced_mcq(
    skill_name: str,
    selected_playlist: dict,
) -> tuple[list[dict], list[int]]:
    """
    Public entry point called by assessment_service.
    Builds context then generates MCQ. Falls back gracefully.
    """
    try:
        from backend.enhanced_assessment.context_builder import build_context

        context = build_context(skill_name)

        # Append playlist info to context for relevance
        summary = selected_playlist.get("summary", {}) or {}
        playlist_context = (
            f"\n\n=== Playlist Context ===\n"
            f"Playlist: {selected_playlist.get('title', '')}\n"
            f"Channel: {selected_playlist.get('channel_title', '')}\n"
            f"Topic overview: {summary.get('topic_overview', '')}\n"
            f"Topics covered: {summary.get('topics_covered_summary', '')}\n"
        )
        full_context = context + playlist_context

        return generate_mcq(skill_name, full_context)
    except Exception:
        return _fallback_questions(skill_name)

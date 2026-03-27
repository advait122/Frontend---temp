import json
import os
from collections import Counter

from backend.roadmap_engine.enhanced_assessment.knowledge import crawler_knowledge_for_skill


MCQ_EASY_COUNT = 4
MCQ_MEDIUM_COUNT = 10
MCQ_HARD_COUNT = 6
MCQ_TOTAL_COUNT = MCQ_EASY_COUNT + MCQ_MEDIUM_COUNT + MCQ_HARD_COUNT
GROQ_MODEL = "llama-3.1-8b-instant"


def build_mcq_assessment(skill_name: str, selected_playlist: dict | None) -> tuple[list[dict], list[int]]:
    generated = _llm_mcq(skill_name, selected_playlist or {})
    if generated:
        return generated
    return _fallback_mcq(skill_name)


def _llm_mcq(skill_name: str, selected_playlist: dict) -> tuple[list[dict], list[int]] | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    summary = selected_playlist.get("summary", {}) if isinstance(selected_playlist, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    topic_overview = str(summary.get("topic_overview", "")).strip()
    learning_experience = str(summary.get("learning_experience", "")).strip()
    topics_covered = str(summary.get("topics_covered_summary", "")).strip()
    knowledge_items = crawler_knowledge_for_skill(skill_name, max_items=12)
    knowledge_text = "\n".join([f"- {item['source_name']}: {item['url']}" for item in knowledge_items])

    prompt = (
        f"Generate exactly {MCQ_TOTAL_COUNT} MCQ questions for {skill_name}.\n"
        "Difficulty mix MUST be exact:\n"
        f"- easy: {MCQ_EASY_COUNT}\n"
        f"- medium: {MCQ_MEDIUM_COUNT}\n"
        f"- hard: {MCQ_HARD_COUNT}\n"
        "Return strict JSON only with this shape:\n"
        "{ \"questions\": ["
        "{ \"topic\": str, \"difficulty\": \"easy\"|\"medium\"|\"hard\", "
        "\"question\": str, \"options\": [str, str, str, str], \"correct_option_index\": 0-3 } ] }\n"
        "No markdown, no comments.\n\n"
        f"Playlist title: {selected_playlist.get('title', '')}\n"
        f"Playlist channel: {selected_playlist.get('channel_title', '')}\n"
        f"Topic overview: {topic_overview}\n"
        f"Learning experience: {learning_experience}\n"
        f"Topics covered summary: {topics_covered}\n"
        f"Crawler references:\n{knowledge_text if knowledge_text else '- None provided'}\n"
    )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You create rigorous assessment questions in strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json(response.choices[0].message.content or "")
        if not parsed:
            return None
        questions, answer_key = _normalize_mcq_payload(parsed.get("questions"))
        if not _is_valid_mix(questions):
            return None
        if len(questions) != MCQ_TOTAL_COUNT:
            return None
        return questions, answer_key
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


def _normalize_mcq_payload(raw_questions: object) -> tuple[list[dict], list[int]]:
    if not isinstance(raw_questions, list):
        return [], []

    questions: list[dict] = []
    answer_key: list[int] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "General")).strip() or "General"
        difficulty = _normalize_difficulty(str(item.get("difficulty", "medium")))
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        if not question or not isinstance(options, list) or len(options) != 4:
            continue
        try:
            answer = int(item.get("correct_option_index"))
        except (TypeError, ValueError):
            continue
        if answer < 0 or answer > 3:
            continue

        questions.append(
            {
                "topic": topic,
                "difficulty": difficulty,
                "question": question,
                "options": [str(opt) for opt in options],
            }
        )
        answer_key.append(answer)

    return questions[:MCQ_TOTAL_COUNT], answer_key[:MCQ_TOTAL_COUNT]


def _normalize_difficulty(value: str) -> str:
    key = value.strip().lower()
    if key in {"easy", "basic"}:
        return "easy"
    if key in {"hard", "advanced"}:
        return "hard"
    return "medium"


def _is_valid_mix(questions: list[dict]) -> bool:
    if len(questions) != MCQ_TOTAL_COUNT:
        return False
    counts = Counter([str(item.get("difficulty", "medium")).lower() for item in questions])
    return (
        counts.get("easy", 0) == MCQ_EASY_COUNT
        and counts.get("medium", 0) == MCQ_MEDIUM_COUNT
        and counts.get("hard", 0) == MCQ_HARD_COUNT
    )


def _fallback_mcq(skill_name: str) -> tuple[list[dict], list[int]]:
    templates = [
        ("easy", "Foundations", "What is the best first step when learning {skill}?"),
        ("easy", "Terminology", "Which option best describes a core concept in {skill}?"),
        ("easy", "Usage", "Where is {skill} most often used in practice?"),
        ("easy", "Basics", "What does a beginner in {skill} need to focus on first?"),
        ("medium", "Problem Solving", "How should you approach a new {skill} problem?"),
        ("medium", "Trade-offs", "Which trade-off is most relevant in {skill} solutions?"),
        ("medium", "Debugging", "What is a strong debugging strategy for {skill}?"),
        ("medium", "Patterns", "When should patterns be used in {skill}?"),
        ("medium", "Complexity", "How should complexity be evaluated in {skill}?"),
        ("medium", "Design", "Which design choice improves maintainability in {skill}?"),
        ("medium", "Quality", "How can you improve correctness in {skill} tasks?"),
        ("medium", "Validation", "Which method best validates a {skill} solution?"),
        ("medium", "Refactoring", "When is refactoring useful in {skill}?"),
        ("medium", "Optimization", "What is a safe optimization approach in {skill}?"),
        ("hard", "Edge Cases", "Which edge-case handling strategy is strongest in {skill}?"),
        ("hard", "Architecture", "How should architecture decisions be made for {skill} systems?"),
        ("hard", "Performance", "Which performance analysis approach is best for {skill}?"),
        ("hard", "Robustness", "What makes a {skill} implementation production-ready?"),
        ("hard", "Reasoning", "Which reasoning style best proves a {skill} solution is correct?"),
        ("hard", "Advanced Practice", "What advanced practice best improves mastery in {skill}?"),
    ]

    questions: list[dict] = []
    answer_key: list[int] = []
    for idx, (difficulty, topic, text) in enumerate(templates, start=1):
        question_text = text.format(skill=skill_name)
        questions.append(
            {
                "topic": topic,
                "difficulty": difficulty,
                "question": question_text,
                "options": [
                    "Use fundamentals, test thoroughly, and verify assumptions.",
                    "Skip fundamentals and focus only on memorized tricks.",
                    "Avoid testing and rely on first attempt output.",
                    "Ignore constraints and edge cases.",
                ],
            }
        )
        answer_key.append(0)

    return questions, answer_key


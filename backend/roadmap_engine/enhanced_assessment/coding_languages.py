from backend.roadmap_engine.services.skill_normalizer import normalize_skill


LANGUAGE_ALIASES = {
    "python": "python",
    "py": "python",
    "python3": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "cxx": "cpp",
    "c": "c",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "rs": "rust",
}

SKILL_LANGUAGE_LOCKS = {
    "python": "python",
    "c++": "cpp",
    "c": "c",
    "java": "java",
    "javascript": "javascript",
    "typescript": "typescript",
    "go": "go",
    "rust": "rust",
}


def normalize_coding_language(language: str) -> str:
    return LANGUAGE_ALIASES.get(str(language or "").strip().lower(), "")


def locked_coding_language_for_skill(skill_name: str) -> str:
    normalized_skill = normalize_skill(skill_name)
    return SKILL_LANGUAGE_LOCKS.get(normalized_skill, "")


def default_supported_languages_for_skill(skill_name: str) -> list[str]:
    locked = locked_coding_language_for_skill(skill_name)
    if locked:
        return [locked]
    return ["python", "cpp"]

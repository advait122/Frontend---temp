from backend.roadmap_engine.services.skill_normalizer import normalize_skill


CODING_SKILL_KEYS = {
    "dsa",
    "python",
    "c++",
    "c",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "problem solving",
    "competitive programming",
}


def requires_coding_test(skill_name: str) -> bool:
    normalized = normalize_skill(skill_name)
    if normalized in CODING_SKILL_KEYS:
        return True
    compact = normalized.replace("-", " ").replace("_", " ").strip()
    tokens = {token for token in compact.split() if token}
    if {"data", "structures", "algorithms"}.issubset(tokens):
        return True
    if "algorithm" in tokens or "algorithms" in tokens:
        return True
    return False


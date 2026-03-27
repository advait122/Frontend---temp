import re


SKILL_ALIAS_MAP = {
    "c plus plus": "c++",
    "cpp": "c++",
    "object oriented programming": "oops",
    "oop": "oops",
    "object oriented design": "oops",
    "data structures and algorithms": "dsa",
    "data structures & algorithms": "dsa",
    "data structures": "dsa",
    "algorithms": "dsa",
    "algorithm": "dsa",
    "problem solving": "dsa",
    "debugging": "debugging",
    "js": "javascript",
    "ml": "machine learning",
    "dl": "deep learning",
    "devops": "devops",
    "docker": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "kubectl": "kubernetes",
    "terraform": "terraform",
    "iac": "terraform",
    "infrastructure as code": "terraform",
    "aws": "cloud",
    "azure": "cloud",
    "gcp": "cloud",
    "cloud computing": "cloud",
    "cloud": "cloud",
    "ci cd": "ci/cd",
    "ci/cd": "ci/cd",
    "continuous integration": "ci/cd",
    "continuous delivery": "ci/cd",
    "continuous deployment": "ci/cd",
    "bash": "shell scripting",
    "shell": "shell scripting",
    "shell scripting": "shell scripting",
    "monitoring": "monitoring",
    "observability": "monitoring",
    "rest": "api",
    "rest api": "api",
    "rest apis": "api",
    "restful api": "api",
    "restful apis": "api",
    "apis": "api",
    "api design": "api",
    "api development": "api",
    "computer networks": "cn",
    "networking": "cn",
    "operating systems": "os",
    "operating system": "os",
    "dbms": "dbms",
    "database management system": "dbms",
    "system design": "system design",
}

DISPLAY_MAP = {
    "c++": "C++",
    "oops": "OOPS",
    "dsa": "DSA",
    "sql": "SQL",
    "api": "API",
    "ci/cd": "CI/CD",
    "cloud": "Cloud",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "shell scripting": "Shell Scripting",
    "cn": "Computer Networks",
    "os": "Operating Systems",
    "dbms": "DBMS",
    "html": "HTML",
    "css": "CSS",
    "javascript": "JavaScript",
}

NON_ROADMAP_SKILLS = {
    "code and system health",
    "system health",
    "data analysis",
    "analysis",
    "technical execution",
    "innovation",
    "productivity",
    "design",
    "social good",
    "economics",
    "finance",
    "computer science",
}


def normalize_skill(skill: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9+ ]+", " ", skill.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    mapped = SKILL_ALIAS_MAP.get(normalized, normalized)
    if mapped in NON_ROADMAP_SKILLS:
        return ""
    return mapped


def display_skill(normalized_skill: str) -> str:
    if normalized_skill in DISPLAY_MAP:
        return DISPLAY_MAP[normalized_skill]
    return normalized_skill.title()


def deduplicate_skills(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for skill in skills:
        key = normalize_skill(skill)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(skill.strip())

    return deduped


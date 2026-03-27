import json
import os
import re
from collections import Counter
from hashlib import sha1
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from backend.roadmap_engine.config import (
    EVIDENCE_CACHE_TTL_HOURS,
    EVIDENCE_FETCH_TIMEOUT_SECONDS,
    SERPAPI_API_KEY,
)
from backend.roadmap_engine.services.skill_normalizer import display_skill, normalize_skill
from backend.roadmap_engine.storage import evidence_cache_repo, opportunities_repo


GROQ_MODEL = "llama-3.3-70b-versatile"

ROLE_KEYWORD_RULES = {
    "backend": ["backend", "api", "server", "django", "flask", "spring", "node"],
    "frontend": ["frontend", "react", "angular", "ui", "web developer"],
    "full_stack": ["full stack", "fullstack", "mern", "mean"],
    "data_ai": ["data scientist", "machine learning", "deep learning", "ai", "ml"],
    "devops": ["devops", "sre", "platform engineer", "site reliability", "infrastructure", "cloud engineer"],
}

ROLE_BASELINE_SKILLS = {
    "backend": ["Python", "Java", "OOPS", "SQL", "DSA", "Git", "Linux"],
    "frontend": ["HTML", "CSS", "JavaScript", "Git", "DSA"],
    "full_stack": ["HTML", "CSS", "JavaScript", "SQL", "Git", "DSA"],
    "data_ai": ["Python", "SQL", "Machine Learning", "Deep Learning", "Git"],
    "devops": ["Linux", "Git", "Docker", "Kubernetes", "Cloud", "CI/CD", "Terraform", "Shell Scripting"],
    "software_engineering": ["DSA", "OOPS", "SQL", "Git"],
}

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
LIVE_FETCH_BLOCKLIST = ("glassdoor.", "indeed.", "linkedin.", "monster.")
SKILL_TEXT_PATTERNS = {
    "python": ["python"],
    "java": ["java"],
    "c++": ["c++", "cpp", "c plus plus"],
    "sql": ["sql", "mysql", "postgresql", "postgres"],
    "javascript": ["javascript", "js", "typescript"],
    "html": ["html"],
    "css": ["css"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "git": ["git", "github"],
    "linux": ["linux"],
    "dsa": ["data structures and algorithms", "data structures", "algorithms", "dsa"],
    "oops": ["object oriented programming", "oop", "oops"],
    "react": ["react", "reactjs"],
    "node": ["node", "nodejs", "node.js"],
    "django": ["django"],
    "flask": ["flask"],
    "spring": ["spring", "spring boot"],
    "api": ["rest api", "apis", "api development", "api design"],
}
INTERVIEW_TOPIC_PATTERNS = {
    "DSA": ["data structures and algorithms", "dsa", "array", "linked list", "tree", "graph", "dynamic programming"],
    "OOPS": ["object oriented programming", "oop", "oops", "inheritance", "polymorphism", "encapsulation"],
    "SQL": ["sql", "joins", "indexing", "normalization", "database queries"],
    "DBMS": ["dbms", "database management system", "transactions", "acid"],
    "OS": ["operating system", "os", "process", "thread", "deadlock"],
    "CN": ["computer networks", "cn", "tcp", "http", "rest"],
    "System Design": ["system design", "scalability", "distributed system", "load balancer"],
    "Projects": ["project discussion", "projects", "resume project", "portfolio"],
}
ROUND_PATTERNS = {
    "Online Assessment": ["online assessment", "oa", "coding round", "aptitude test"],
    "Technical Interview": ["technical interview", "technical round", "coding interview"],
    "Machine Coding": ["machine coding", "build a small app", "implementation round"],
    "System Design Round": ["system design round", "design round"],
    "HR Round": ["hr round", "behavioral round", "managerial round"],
}
PROJECT_SIGNAL_PATTERNS = {
    "Backend API Project": ["rest api", "crud app", "backend project", "api development"],
    "Database Project": ["sql project", "database design", "schema design"],
    "Frontend Project": ["frontend project", "react app", "responsive web app"],
    "ML Project": ["machine learning project", "model building", "deep learning project"],
}
INTERVIEW_TOPIC_TO_SKILLS = {
    "DSA": ["DSA"],
    "OOPS": ["OOPS"],
    "SQL": ["SQL"],
    "DBMS": ["SQL"],
    "OS": ["Linux"],
    "CN": ["API"],
    "System Design": ["API", "SQL"],
    "Projects": ["Git"],
}
SOURCE_TYPE_WEIGHTS = {
    "live_job_post": 1.4,
    "live_public_page": 1.1,
    "unknown": 1.0,
}
ROLE_SEQUENCE_PRIORITIES = {
    "backend": ["DSA", "OOPS", "SQL", "Python", "Java", "API", "Git", "Linux"],
    "frontend": ["HTML", "CSS", "JavaScript", "React", "Git", "DSA"],
    "full_stack": ["HTML", "CSS", "JavaScript", "SQL", "API", "Git", "DSA"],
    "data_ai": ["Python", "SQL", "Machine Learning", "Deep Learning", "Git"],
    "devops": ["Linux", "Shell Scripting", "Git", "Docker", "CI/CD", "Cloud", "Terraform", "Kubernetes", "Monitoring"],
    "software_engineering": ["DSA", "OOPS", "SQL", "Python", "Java", "Git", "Linux", "API"],
}
ROLE_ALLOWED_SKILLS = {
    "backend": {"dsa", "oops", "sql", "python", "java", "c++", "git", "linux", "api", "dbms", "os", "cn", "system design"},
    "frontend": {"html", "css", "javascript", "react", "git", "dsa", "api"},
    "full_stack": {"html", "css", "javascript", "react", "sql", "api", "git", "dsa", "python", "java", "node"},
    "data_ai": {"python", "sql", "machine learning", "deep learning", "git", "dsa"},
    "devops": {"linux", "git", "docker", "kubernetes", "cloud", "ci/cd", "terraform", "shell scripting", "monitoring", "python", "api", "cn"},
    "software_engineering": {"dsa", "oops", "sql", "python", "java", "c++", "git", "linux", "api", "dbms", "os", "cn"},
}


def _extract_json_object(raw_text: str) -> dict | None:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _heuristic_company(goal_text: str, company_candidates: list[str]) -> str | None:
    lowered_goal = goal_text.lower()

    for company in company_candidates:
        if company.lower() in lowered_goal:
            return company

    pattern = re.compile(r"\b(?:in|at|for)\s+([a-zA-Z0-9][a-zA-Z0-9 .&-]{1,40})", re.IGNORECASE)
    match = pattern.search(goal_text)
    if match:
        candidate = match.group(1).strip(" .")
        lowered_candidate = candidate.lower()
        invalid_tokens = {
            "internship",
            "job",
            "role",
            "months",
            "month",
            "weeks",
            "week",
            "days",
            "day",
        }
        if any(token in lowered_candidate.split() for token in invalid_tokens):
            return None
        return candidate

    return None


def parse_goal_text(goal_text: str) -> dict:
    company_candidates = opportunities_repo.list_company_names()
    fallback_company = _heuristic_company(goal_text, company_candidates)
    fallback = {
        "target_company": fallback_company,
        "target_role_family": "Software Engineering",
        "confidence": 0.45,
    }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return fallback

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "Extract structured goal details from the text. "
            "Return JSON only with keys: target_company, target_role_family, confidence. "
            "confidence must be between 0 and 1.\n\n"
            f"Goal text: {goal_text}\n"
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured career-goal information in strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json_object(response.choices[0].message.content or "")
        if not parsed:
            return fallback

        target_company = parsed.get("target_company") or fallback_company
        target_role_family = parsed.get("target_role_family") or "Software Engineering"
        confidence = parsed.get("confidence")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = fallback["confidence"]

        normalized_company = None
        if target_company:
            company_lower = target_company.strip().lower()
            for company in company_candidates:
                if company.lower() == company_lower:
                    normalized_company = company
                    break
            if normalized_company is None:
                normalized_company = target_company.strip()

        return {
            "target_company": normalized_company,
            "target_role_family": target_role_family.strip(),
            "confidence": max(0.0, min(1.0, confidence)),
        }
    except Exception:
        return fallback


def _skill_counter_from_opportunities(opportunities: list[dict]) -> Counter:
    counter: Counter = Counter()
    display_lookup: dict[str, str] = {}
    for item in opportunities:
        skill_names = list(item.get("skills_list", []))
        skill_names.extend(_extract_skills_from_text(str(item.get("raw_text", ""))))
        skill_names = _clean_skill_candidates(skill_names, item.get("role_intent"))
        for skill in skill_names:
            normalized = normalize_skill(skill)
            if not normalized:
                continue
            counter[normalized] += 1
            display_lookup.setdefault(normalized, skill.strip() or display_skill(normalized))
    counter.display_lookup = display_lookup  # type: ignore[attr-defined]
    return counter


def _extract_skills_from_text(raw_text: str) -> list[str]:
    lowered = f" {raw_text.lower()} "
    found: list[str] = []
    for canonical, patterns in SKILL_TEXT_PATTERNS.items():
        if any(f" {pattern} " in lowered for pattern in patterns):
            found.append(display_skill(canonical))
    return found


def _clean_skill_candidates(skills: list[str], role_intent: dict | None = None) -> list[str]:
    role_family = str((role_intent or {}).get("normalized_role_family") or "software_engineering")
    allowed_skills = ROLE_ALLOWED_SKILLS.get(role_family, ROLE_ALLOWED_SKILLS["software_engineering"])
    cleaned: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        normalized = normalize_skill(skill)
        if not normalized or normalized in seen:
            continue
        if normalized not in allowed_skills:
            continue
        seen.add(normalized)
        cleaned.append(display_skill(normalized))
    return cleaned


def _extract_pattern_matches(raw_text: str, patterns: dict[str, list[str]]) -> list[str]:
    lowered = f" {raw_text.lower()} "
    matches: list[str] = []
    for label, values in patterns.items():
        if any(f" {value} " in lowered for value in values):
            matches.append(label)
    return matches


def _record_weight(record: dict) -> float:
    return float(SOURCE_TYPE_WEIGHTS.get(str(record.get("source_type") or "unknown"), 1.0))


def _counter_to_ranked(counter: dict[str, float], limit: int = 8) -> list[dict]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "label": label,
            "score": round(score, 2),
        }
        for label, score in ranked[:limit]
    ]


def _extract_signal_summary(records: list[dict]) -> dict:
    topic_scores: dict[str, float] = {}
    round_scores: dict[str, float] = {}
    project_scores: dict[str, float] = {}

    for record in records:
        raw_text = str(record.get("raw_text", ""))
        if not raw_text:
            continue
        weight = _record_weight(record)
        for label in _extract_pattern_matches(raw_text, INTERVIEW_TOPIC_PATTERNS):
            topic_scores[label] = topic_scores.get(label, 0.0) + weight
        for label in _extract_pattern_matches(raw_text, ROUND_PATTERNS):
            round_scores[label] = round_scores.get(label, 0.0) + weight
        for label in _extract_pattern_matches(raw_text, PROJECT_SIGNAL_PATTERNS):
            project_scores[label] = project_scores.get(label, 0.0) + weight

    return {
        "top_interview_topics": _counter_to_ranked(topic_scores, limit=6),
        "top_round_patterns": _counter_to_ranked(round_scores, limit=5),
        "project_expectations": _counter_to_ranked(project_scores, limit=4),
    }


def _normalize_role_family(goal_text: str, parsed_role_family: str | None) -> str:
    combined = f"{parsed_role_family or ''} {goal_text}".lower()
    for role_family, keywords in ROLE_KEYWORD_RULES.items():
        if any(keyword in combined for keyword in keywords):
            return role_family
    return "software_engineering"


def _derive_search_keywords(goal_text: str, target_company: str | None, role_family: str) -> list[str]:
    keywords: list[str] = []
    lowered_goal = goal_text.lower().strip()
    if lowered_goal:
        keywords.append(lowered_goal)

    role_family_queries = {
        "backend": ["backend developer", "software engineer backend", "api developer"],
        "frontend": ["frontend developer", "react developer", "web developer"],
        "full_stack": ["full stack developer", "mern developer", "software engineer full stack"],
        "data_ai": ["machine learning engineer", "data scientist", "ai engineer"],
        "devops": ["devops engineer", "site reliability engineer", "cloud engineer", "platform engineer"],
        "software_engineering": ["software engineer", "developer", "programmer"],
    }
    keywords.extend(role_family_queries.get(role_family, []))

    if target_company:
        keywords.append(target_company)

    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        cleaned = " ".join((keyword or "").split()).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped[:6]


def _build_role_intent(
    goal_text: str,
    target_company: str | None,
    parsed_role_family: str | None,
    target_duration_months: int,
) -> dict:
    normalized_role_family = _normalize_role_family(goal_text, parsed_role_family)
    return {
        "goal_text": goal_text,
        "target_company": target_company,
        "parsed_role_family": parsed_role_family,
        "normalized_role_family": normalized_role_family,
        "search_keywords": _derive_search_keywords(goal_text, target_company, normalized_role_family),
        "target_duration_months": int(target_duration_months),
    }


def _role_relevance_score(role_intent: dict, text: str) -> float:
    lowered = f" {text.lower()} "
    role_family = str(role_intent.get("normalized_role_family") or "software_engineering")
    score = 0.0

    for keyword in ROLE_KEYWORD_RULES.get(role_family, []):
        if f" {keyword} " in lowered:
            score += 1.0

    for keyword in role_intent.get("search_keywords", [])[:4]:
        normalized_keyword = f" {' '.join(str(keyword).lower().split())} "
        if normalized_keyword in lowered:
            score += 1.5

    target_company = str(role_intent.get("target_company") or "").strip().lower()
    if target_company and f" {target_company} " in lowered:
        score += 2.0

    return score


def _attach_relevance(record: dict, role_intent: dict) -> dict:
    text_parts = [
        str(record.get("title") or ""),
        str(record.get("company") or ""),
        str(record.get("raw_text") or ""),
    ]
    score = _role_relevance_score(role_intent, " ".join(part for part in text_parts if part))
    record_copy = dict(record)
    record_copy["relevance_score"] = round(score, 2)
    return record_copy


def _filter_ranked_records(role_intent: dict, records: list[dict], min_score: float) -> list[dict]:
    ranked = [_attach_relevance(record, role_intent) for record in records]
    ranked.sort(
        key=lambda item: (
            -float(item.get("relevance_score", 0.0)),
            -_record_weight(item),
            str(item.get("title") or ""),
        )
    )
    kept = [item for item in ranked if float(item.get("relevance_score", 0.0)) >= min_score]
    if kept:
        return kept
    return ranked[: min(8, len(ranked))]


def _role_cache_key(role_intent: dict) -> str:
    payload = {
        "goal_text": role_intent.get("goal_text"),
        "target_company": role_intent.get("target_company"),
        "normalized_role_family": role_intent.get("normalized_role_family"),
        "search_keywords": role_intent.get("search_keywords", []),
        "target_duration_months": role_intent.get("target_duration_months"),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return sha1(serialized.encode("utf-8")).hexdigest()


def _serpapi_search(*, engine: str, query: str, num: int = 5) -> dict:
    if not SERPAPI_API_KEY:
        return {}

    try:
        response = requests.get(
            SERPAPI_SEARCH_URL,
            params={
                "engine": engine,
                "q": query,
                "api_key": SERPAPI_API_KEY,
                "hl": "en",
                "num": num,
            },
            timeout=EVIDENCE_FETCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _is_fetchable_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if any(blocked in host for blocked in LIVE_FETCH_BLOCKLIST):
        return False
    return True


def _fetch_public_page_text(url: str) -> str:
    if not _is_fetchable_public_url(url):
        return ""

    try:
        response = requests.get(
            url,
            timeout=EVIDENCE_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 PathForge/1.0"},
        )
        response.raise_for_status()
    except Exception:
        return ""

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type:
        return ""

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        text = " ".join(soup.stripped_strings)
    except Exception:
        return ""

    return re.sub(r"\s+", " ", text).strip()[:6000]


def _collect_live_job_evidence(role_intent: dict) -> list[dict]:
    records: list[dict] = []
    seen_urls: set[str] = set()
    for keyword in role_intent.get("search_keywords", [])[:3]:
        payload = _serpapi_search(engine="google_jobs", query=str(keyword), num=5)
        for item in payload.get("jobs_results", [])[:5]:
            title = str(item.get("title") or "").strip()
            company = str(item.get("company_name") or "").strip()
            description = str(item.get("description") or "").strip()
            link = str(item.get("share_link") or "").strip()
            if link and link in seen_urls:
                continue
            if link:
                seen_urls.add(link)
            raw_text = " ".join(part for part in [title, company, description] if part)
            if not raw_text:
                continue
            records.append(
                {
                    "source_type": "live_job_post",
                    "source_name": "serpapi_google_jobs",
                    "title": title,
                    "company": company,
                    "url": link,
                    "skills_list": _clean_skill_candidates(_extract_skills_from_text(raw_text), role_intent),
                    "raw_text": raw_text,
                    "role_intent": role_intent,
                }
            )
    return _filter_ranked_records(role_intent, records, min_score=1.0)


def _collect_live_page_evidence(role_intent: dict) -> list[dict]:
    records: list[dict] = []
    seen_urls: set[str] = set()
    role_query = next(iter(role_intent.get("search_keywords", [])), "")
    if not role_query:
        return records

    search_query = f"{role_query} interview experience OR job requirements"
    payload = _serpapi_search(engine="google", query=search_query, num=6)
    for item in payload.get("organic_results", [])[:6]:
        link = str(item.get("link") or "").strip()
        if not link or link in seen_urls or not _is_fetchable_public_url(link):
            continue
        seen_urls.add(link)
        page_text = _fetch_public_page_text(link)
        if len(page_text) < 200:
            continue
        title = str(item.get("title") or "").strip()
        records.append(
            {
                "source_type": "live_public_page",
                "source_name": "serpapi_google_search",
                "title": title,
                "company": "",
                "url": link,
                "skills_list": _clean_skill_candidates(_extract_skills_from_text(page_text), role_intent),
                "raw_text": page_text,
                "role_intent": role_intent,
            }
        )
    return _filter_ranked_records(role_intent, records, min_score=1.2)


def _collect_local_evidence(role_intent: dict) -> list[dict]:
    evidence: list[dict] = []
    seen_keys: set[str] = set()
    target_company = role_intent.get("target_company")
    search_keywords = role_intent.get("search_keywords", [])

    if target_company:
        for item in opportunities_repo.list_by_company(str(target_company), limit=80):
            key = f"local:{item['id']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            item_copy = dict(item)
            item_copy["role_intent"] = role_intent
            item_copy["skills_list"] = _clean_skill_candidates(list(item.get("skills_list", [])), role_intent)
            evidence.append(item_copy)

    for keyword in search_keywords[:4]:
        for item in opportunities_repo.list_opportunities(search=str(keyword))[:40]:
            key = f"local:{item['id']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            item_copy = dict(item)
            item_copy["role_intent"] = role_intent
            item_copy["skills_list"] = _clean_skill_candidates(list(item.get("skills_list", [])), role_intent)
            evidence.append(item_copy)
    return _filter_ranked_records(role_intent, evidence, min_score=0.5)


def _collect_evidence_records(role_intent: dict) -> list[dict]:
    cache_key = _role_cache_key(role_intent)
    cached = evidence_cache_repo.get_fresh_cache(cache_key, EVIDENCE_CACHE_TTL_HOURS)
    if cached is not None:
        return list(cached.get("evidence", []))

    live_records = _collect_live_job_evidence(role_intent) + _collect_live_page_evidence(role_intent)
    local_records = _collect_local_evidence(role_intent)
    evidence = live_records + local_records
    trimmed_evidence = evidence[:120]
    source_summary = {
        "cache_hit": False,
        "live_job_post_count": len([item for item in live_records if item.get("source_type") == "live_job_post"]),
        "live_public_page_count": len([item for item in live_records if item.get("source_type") == "live_public_page"]),
        "local_record_count": len(local_records),
    }
    evidence_cache_repo.upsert_cache(
        role_cache_key=cache_key,
        role_family=str(role_intent.get("normalized_role_family") or ""),
        target_company=role_intent.get("target_company"),
        evidence=trimmed_evidence,
        source_summary=source_summary,
    )
    return trimmed_evidence


def _summarize_evidence(records: list[dict]) -> dict:
    skill_counter = _skill_counter_from_opportunities(records)
    display_lookup = getattr(skill_counter, "display_lookup", {})
    top_skills = [
        {
            "skill": display_lookup.get(key, display_skill(key)),
            "normalized_skill": key,
            "count": count,
        }
        for key, count in skill_counter.most_common(8)
    ]
    companies = sorted({str(item.get("company", "")).strip() for item in records if item.get("company")})
    source_breakdown = Counter(str(item.get("source_type") or "unknown") for item in records)
    signal_summary = _extract_signal_summary(records)
    average_relevance = round(
        sum(float(item.get("relevance_score", 0.0)) for item in records) / max(len(records), 1),
        2,
    ) if records else 0.0
    return {
        "sample_size": len(records),
        "top_skills": top_skills,
        "companies": companies[:10],
        "source_breakdown": dict(source_breakdown),
        "average_relevance_score": average_relevance,
        "top_interview_topics": signal_summary.get("top_interview_topics", []),
        "top_round_patterns": signal_summary.get("top_round_patterns", []),
        "project_expectations": signal_summary.get("project_expectations", []),
    }


def _limit_required_skills(required_skills: list[str], target_duration_months: int) -> list[str]:
    if target_duration_months <= 6:
        limit = 8
    elif target_duration_months <= 12:
        limit = 10
    else:
        limit = 12
    return required_skills[:limit]


def _skill_limit_for_duration(target_duration_months: int) -> int:
    return len(_limit_required_skills(["x"] * 20, target_duration_months))


def _role_baseline_skills(role_intent: dict) -> list[str]:
    role_family = role_intent.get("normalized_role_family", "software_engineering")
    baseline = list(ROLE_BASELINE_SKILLS.get(role_family, ROLE_BASELINE_SKILLS["software_engineering"]))

    goal_text = str(role_intent.get("goal_text", "")).lower()
    if "intern" in goal_text and "Git" not in baseline:
        baseline.append("Git")
    return _clean_skill_candidates(baseline, role_intent)


def _priority_map_for_role(role_intent: dict) -> dict[str, int]:
    role_family = role_intent.get("normalized_role_family", "software_engineering")
    priorities = ROLE_SEQUENCE_PRIORITIES.get(role_family, ROLE_SEQUENCE_PRIORITIES["software_engineering"])
    return {normalize_skill(skill): index for index, skill in enumerate(priorities)}


def _ranked_labels(items: list[dict], limit: int = 4) -> list[str]:
    labels: list[str] = []
    for item in items[:limit]:
        label = str(item.get("label") or item.get("skill") or "").strip()
        if label:
            labels.append(label)
    return labels


def _build_validation_result(
    *,
    role_intent: dict,
    draft_skills: list[str],
    validated_skills: list[str],
    evidence_summary: dict,
    known_skills: list[str],
) -> dict:
    draft_keys = [normalize_skill(skill) for skill in draft_skills if normalize_skill(skill)]
    validated_keys = [normalize_skill(skill) for skill in validated_skills if normalize_skill(skill)]
    known_keys = {normalize_skill(skill) for skill in known_skills if normalize_skill(skill)}

    missing_skills = [skill for skill in validated_skills if normalize_skill(skill) not in draft_keys]
    suggested_missing_skills = [skill for skill in validated_skills if normalize_skill(skill) not in known_keys]
    weak_skills = [
        skill for skill in validated_skills[:5]
        if normalize_skill(skill) not in known_keys and normalize_skill(skill) in draft_keys
    ]
    overemphasized_topics = [skill for skill in draft_skills if normalize_skill(skill) not in validated_keys][:3]

    interview_topics = _ranked_labels(evidence_summary.get("top_interview_topics", []), limit=4)
    round_patterns = _ranked_labels(evidence_summary.get("top_round_patterns", []), limit=4)
    project_expectations = _ranked_labels(evidence_summary.get("project_expectations", []), limit=3)

    missing_interview_prep = [
        topic for topic in interview_topics
        if any(
            normalize_skill(mapped_skill) not in validated_keys
            for mapped_skill in INTERVIEW_TOPIC_TO_SKILLS.get(topic, [])
        )
    ]

    priority_map = _priority_map_for_role(role_intent)
    sequence_adjustments: list[str] = []
    for skill in validated_skills[:5]:
        key = normalize_skill(skill)
        if key in priority_map and priority_map[key] <= 2:
            sequence_adjustments.append(f"Move {skill} into the early roadmap foundation.")
    if "Technical Interview" in round_patterns and "DSA" in validated_skills:
        sequence_adjustments.append("Start interview-style problem solving in parallel with skill learning.")
    deduped_sequence_adjustments = list(dict.fromkeys(sequence_adjustments))[:4]

    scope_risks: list[str] = []
    skill_limit = _skill_limit_for_duration(int(role_intent.get("target_duration_months", 6)))
    if len(validated_skills) >= skill_limit:
        scope_risks.append(
            f"Timeline is tight; keep the roadmap focused on the top {skill_limit} priority skills."
        )
    if len(project_expectations) > 1 and int(role_intent.get("target_duration_months", 6)) <= 6:
        scope_risks.append("Project breadth should stay narrow; prefer one strong project over many shallow ones.")
    if len(interview_topics) >= 3 and int(role_intent.get("target_duration_months", 6)) <= 6:
        scope_risks.append("Interview prep needs to begin early because topic coverage is broad for the target role.")

    notes: list[str] = []
    evidence_top = _ranked_labels(evidence_summary.get("top_skills", []), limit=3)
    if evidence_top:
        notes.append(f"Top opportunity signals: {', '.join(evidence_top)}.")
    elif int(evidence_summary.get("sample_size", 0)) == 0:
        notes.append("Validation relied on goal intent and roadmap heuristics because no strong market matches were cached.")
    if float(evidence_summary.get("average_relevance_score", 0.0)) > 0:
        notes.append(f"Evidence quality score: {evidence_summary.get('average_relevance_score')}.")
    if interview_topics:
        notes.append(f"Interview themes detected: {', '.join(interview_topics)}.")
    if round_patterns:
        notes.append(f"Common evaluation rounds: {', '.join(round_patterns)}.")
    if project_expectations:
        notes.append(f"Recommended project direction: {', '.join(project_expectations)}.")
    if int(evidence_summary.get("source_breakdown", {}).get("live_job_post", 0)) > 0:
        notes.append("Live job-market evidence was included in roadmap validation.")
    if suggested_missing_skills:
        notes.append(
            f"Prioritized missing skills for roadmap focus: {', '.join(suggested_missing_skills[:4])}."
        )

    return {
        "required_skills": validated_skills,
        "missing_skills": missing_skills[:6],
        "suggested_missing_skills": suggested_missing_skills[:6],
        "weak_skills": weak_skills[:4],
        "overemphasized_topics": overemphasized_topics,
        "missing_interview_prep": missing_interview_prep,
        "sequence_adjustments": deduped_sequence_adjustments,
        "scope_risks": scope_risks,
        "project_recommendations": project_expectations,
        "round_patterns": round_patterns,
        "interview_topics": interview_topics,
        "notes": notes,
    }


def _validate_required_skills(
    *,
    role_intent: dict,
    draft_skills: list[str],
    evidence_summary: dict,
    known_skills: list[str],
) -> dict:
    scores: dict[str, float] = {}
    labels: dict[str, str] = {}
    priority_map = _priority_map_for_role(role_intent)
    cleaned_draft_skills = _clean_skill_candidates(draft_skills, role_intent)

    for index, skill in enumerate(cleaned_draft_skills):
        normalized = normalize_skill(skill)
        if not normalized:
            continue
        scores[normalized] = scores.get(normalized, 0.0) + max(1.0, 10.0 - index)
        labels.setdefault(normalized, skill.strip())

    if int(evidence_summary.get("sample_size", 0)) >= 3:
        for item in evidence_summary.get("top_skills", []):
            normalized = normalize_skill(str(item.get("normalized_skill") or item.get("skill") or ""))
            if not normalized:
                continue
            count = int(item.get("count", 0))
            scores[normalized] = scores.get(normalized, 0.0) + min(6.0, 1.5 + (count * 0.5))
            labels.setdefault(normalized, str(item.get("skill") or display_skill(normalized)).strip())
        for topic in evidence_summary.get("top_interview_topics", []):
            topic_label = str(topic.get("label") or "").strip()
            topic_score = float(topic.get("score", 0.0))
            for suggested_skill in INTERVIEW_TOPIC_TO_SKILLS.get(topic_label, []):
                normalized = normalize_skill(suggested_skill)
                if not normalized:
                    continue
                scores[normalized] = scores.get(normalized, 0.0) + min(4.0, 0.8 + topic_score)
                labels.setdefault(normalized, suggested_skill)

    for skill in _role_baseline_skills(role_intent):
        normalized = normalize_skill(skill)
        if not normalized:
            continue
        scores[normalized] = scores.get(normalized, 0.0) + 3.0
        labels.setdefault(normalized, skill.strip())

    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -item[1],
            priority_map.get(item[0], 999),
            item[0],
        ),
    )
    validated_skills = [labels[key] for key, _ in ranked]
    validated_skills = _clean_skill_candidates(validated_skills, role_intent)
    validated_skills = _limit_required_skills(
        validated_skills,
        int(role_intent.get("target_duration_months", 6)),
    )
    return _build_validation_result(
        role_intent=role_intent,
        draft_skills=cleaned_draft_skills,
        validated_skills=validated_skills,
        evidence_summary=evidence_summary,
        known_skills=known_skills,
    )


def build_validated_goal_requirements(
    *,
    goal_text: str,
    target_duration_months: int,
    known_skills: list[str] | None = None,
) -> dict:
    known_skills = known_skills or []
    goal_parse = parse_goal_text(goal_text)
    role_intent = _build_role_intent(
        goal_text,
        goal_parse.get("target_company"),
        goal_parse.get("target_role_family"),
        target_duration_months,
    )
    evidence_records = _collect_evidence_records(role_intent)
    evidence_summary = _summarize_evidence(evidence_records)
    draft_requirements = synthesize_required_skills(
        goal_text=goal_text,
        target_company=goal_parse.get("target_company"),
    )
    validation_result = _validate_required_skills(
        role_intent=role_intent,
        draft_skills=list(draft_requirements.get("required_skills", [])),
        evidence_summary=evidence_summary,
        known_skills=known_skills,
    )
    return {
        "goal_parse": goal_parse,
        "role_intent": role_intent,
        "required_skills": validation_result.get("required_skills", []),
        "source": "validated_goal_intelligence_v2",
        "source_opportunity_count": evidence_summary.get("sample_size", 0),
        "rationale": draft_requirements.get("rationale", ""),
        "evidence_summary": evidence_summary,
        "evidence_highlights": validation_result.get("notes", []),
        "validation_result": validation_result,
        "draft_requirements": draft_requirements,
    }


def _fallback_required_skills(goal_text: str, target_company: str | None) -> list[str]:
    opportunities = opportunities_repo.list_by_company(target_company, limit=200) if target_company else []
    counter = _skill_counter_from_opportunities(opportunities)
    display_lookup = getattr(counter, "display_lookup", {})

    if counter:
        top = [display_lookup[key] for key, _ in counter.most_common(10)]
        return _clean_skill_candidates(top, {"normalized_role_family": "software_engineering"})

    baseline = ["DSA", "OOPS", "SQL", "Python", "C++", "Java"]
    lowered_goal = goal_text.lower()
    if "frontend" in lowered_goal:
        baseline.extend(["JavaScript", "HTML", "CSS"])
    if "ai" in lowered_goal or "ml" in lowered_goal:
        baseline.extend(["Machine Learning", "Deep Learning"])
    return _clean_skill_candidates(baseline, {"normalized_role_family": "software_engineering"})


def synthesize_required_skills(goal_text: str, target_company: str | None) -> dict:
    opportunities = opportunities_repo.list_by_company(target_company, limit=120) if target_company else []
    fallback_skills = _fallback_required_skills(goal_text, target_company)

    sample_postings = []
    for item in opportunities[:10]:
        sample_postings.append(
            {
                "title": item.get("title"),
                "type": item.get("type"),
                "skills": item.get("skills_list", []),
            }
        )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not sample_postings:
        return {
            "required_skills": fallback_skills,
            "source": "opportunity_frequency_fallback",
            "source_opportunity_count": len(opportunities),
        }

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "Given career goal text and opportunity samples, produce a practical skill list.\n"
            "Return JSON only with keys required_skills (array of strings) and rationale (short string).\n"
            "Keep required_skills to 6-15 items ordered by priority.\n\n"
            f"Goal text: {goal_text}\n"
            f"Target company: {target_company}\n"
            f"Opportunity samples: {json.dumps(sample_postings, ensure_ascii=False)}\n"
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You infer required skills from job/hackathon opportunity data in strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        parsed = _extract_json_object(response.choices[0].message.content or "")
        if not parsed:
            raise ValueError("Invalid JSON from LLM")

        skills = parsed.get("required_skills")
        if not isinstance(skills, list) or len(skills) == 0:
            raise ValueError("Missing required_skills")

        cleaned = []
        seen = set()
        for skill in skills:
            text = str(skill).strip()
            if not text:
                continue
            key = normalize_skill(text)
            if not key or key in seen:
                continue
            seen.add(key)
            cleaned.append(text)

        if not cleaned:
            raise ValueError("No valid skills after cleanup")

        return {
            "required_skills": cleaned,
            "source": "llm_from_company_opportunities",
            "source_opportunity_count": len(opportunities),
            "rationale": parsed.get("rationale", ""),
        }
    except Exception:
        return {
            "required_skills": fallback_skills,
            "source": "opportunity_frequency_fallback",
            "source_opportunity_count": len(opportunities),
        }

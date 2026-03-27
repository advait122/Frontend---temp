from urllib.parse import urlparse, urlunparse

from config.companies import COMPANIES
from pipeline.crawler.page_fetcher import fetch_page
from pipeline.discovery.devpost_fetcher import fetch_devpost_hackathons
from pipeline.discovery.sitemap_fetcher import fetch_sitemap
from pipeline.llm.llm_extractor import extract_opportunity_with_llm
from pipeline.storage.sqlite_db import delete_expired_opportunities, init_db, upsert_opportunity
from utils.hash_utils import generate_content_hash
from utils.link_extractor import extract_internal_links
from utils.text_cleaner import extract_clean_text


def _normalize_http_url(raw_url: str) -> str:
    candidate = str(raw_url or "").strip()
    if not candidate:
        return ""

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return ""

    netloc = parsed.netloc.strip().lower()
    if not netloc:
        return ""

    # Common typo guard, for example: devpost.ccom -> devpost.com
    if netloc.endswith(".ccom"):
        netloc = f"{netloc[:-5]}.com"

    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in urls:
        normalized = _normalize_http_url(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _normalize_llm_payload(data: dict | list | None) -> dict | None:
    if isinstance(data, list):
        if not data:
            return None
        data = data[0]

    if not isinstance(data, dict):
        return None

    title = str(data.get("title") or "").strip()
    if not title:
        return None

    company = str(data.get("company") or "").strip() or None
    opportunity_type = str(data.get("type") or "").strip().lower() or None
    deadline = data.get("deadline")
    if deadline is not None:
        deadline = str(deadline).strip() or None

    raw_skills = data.get("skills")
    clean_skills: list[str] = []
    if isinstance(raw_skills, list):
        seen_skill_keys: set[str] = set()
        for skill in raw_skills:
            cleaned = str(skill or "").strip()
            if not cleaned:
                continue
            skill_key = cleaned.casefold()
            if skill_key in seen_skill_keys:
                continue
            seen_skill_keys.add(skill_key)
            clean_skills.append(cleaned)

    return {
        "title": title,
        "company": company,
        "type": opportunity_type,
        "deadline": deadline,
        "skills": clean_skills,
    }


def process_company(company: dict) -> None:
    print("\n==============================")
    print(f"Processing: {company['name']}")
    print("==============================")

    # Discovery
    if company["name"] == "Devpost":
        urls = fetch_devpost_hackathons()
    elif "seed_urls" in company:
        urls = company["seed_urls"]
    elif company["use_sitemap"]:
        urls = fetch_sitemap(company["base_url"])
    else:
        urls = []

    urls = _dedupe_urls(urls)
    print(f"Total URLs discovered: {len(urls)}")

    for source_url in urls:
        print(f"\nProcessing URL: {source_url}")
        source_html = fetch_page(source_url)
        if not source_html:
            print("Skipping source URL because the page could not be fetched.")
            continue

        if "seed_urls" in company:
            discovered_links = _dedupe_urls(extract_internal_links(source_html, source_url))
            print(f"Found {len(discovered_links)} internal links")
            target_urls = discovered_links
        else:
            target_urls = [source_url]

        for target_url in target_urls:
            print(f"Processing target: {target_url}")

            page_html = fetch_page(target_url)
            if not page_html:
                print("Skipping target because the page could not be fetched.")
                continue

            clean_text = extract_clean_text(page_html)
            if not clean_text:
                print("Skipping target because no readable text was extracted.")
                continue

            content_hash = generate_content_hash(clean_text)

            try:
                extracted = extract_opportunity_with_llm(clean_text)
            except Exception as error:
                # Keep the pipeline alive even if one page fails.
                print(f"LLM extraction failed for {target_url}: {error}")
                continue

            normalized = _normalize_llm_payload(extracted)
            if not normalized:
                print("Skipping target because extraction result was empty or invalid.")
                continue

            upsert_opportunity(
                data=normalized,
                content_hash=content_hash,
                source="crawler",
                url=target_url,
            )


def main() -> None:
    print("Web Data Pipeline Started")

    init_db()
    delete_expired_opportunities()

    for company in COMPANIES:
        process_company(company)


if __name__ == "__main__":
    main()

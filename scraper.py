import requests
from typing import Optional

import config

LIST_API = "https://jobright.ai/swan/recommend/list/jobs"
FILTER_API = "https://jobright.ai/swan/filter/get/filter"

ROLE_KEYWORDS = [
    "full stack", "fullstack", "full-stack",
    "frontend", "front end", "front-end",
    "backend", "back end", "back-end",
    "python",
    "c++", "c/c++",
    "software engineer", "software developer", "swe",
    "engineer",
]

INTERNSHIP_KEYWORDS = ["intern", "internship", "co-op", "coop"]


def _matches_filter(job: dict) -> bool:
    title = (job.get("jobTitle") or job.get("title") or "").lower()
    seniority = (job.get("jobSeniority") or "").lower()
    is_internship = (
        any(k in seniority for k in INTERNSHIP_KEYWORDS)
        or any(k in title for k in INTERNSHIP_KEYWORDS)
    )
    is_target_role = any(k in title for k in ROLE_KEYWORDS)
    return is_internship and is_target_role


def _normalize_job(raw: dict) -> Optional[dict]:
    job_id = raw.get("jobId") or raw.get("id")
    if not job_id:
        return None
    title = raw.get("jobTitle") or raw.get("title") or "Unknown Title"
    company = (
        raw.get("companyName")
        or raw.get("name")
        or raw.get("company")
        or "Unknown Company"
    )
    location = (
        raw.get("jobLocation")
        or raw.get("location")
        or ("Remote" if raw.get("isRemote") else "Unknown Location")
    )
    job_url = raw.get("url") or f"https://jobright.ai/jobs/info/{job_id}"
    match_score = raw.get("matchScore") or raw.get("score")
    salary = raw.get("salaryDesc") or raw.get("salary") or None
    posted_at = raw.get("publishTimeDesc") or raw.get("publishTime") or None
    work_model = raw.get("workModel") or None
    return {
        "id": str(job_id),
        "title": title,
        "company": company,
        "location": location,
        "url": job_url,
        "matchScore": match_score,
        "salary": salary,
        "postedAt": posted_at,
        "workModel": work_model,
    }


def _extract_items(job_list: list) -> list:
    """Merge jobResult + companyResult into a flat dict per job."""
    captured = []
    for item in job_list:
        job_result = item.get("jobResult", {})
        company_result = item.get("companyResult", {})
        merged = {**job_result, **company_result}
        captured.append(merged)
    return captured


async def scrape_jobs() -> list[dict]:
    session = requests.Session()
    session.cookies.set("SESSION_ID", config.JOBRIGHT_SESSION_ID, domain="jobright.ai")
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "referer": "https://jobright.ai/jobs/recommend",
        "x-client-type": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    })

    # Get saved filter state
    filter_data = {}
    try:
        filter_resp = session.post(FILTER_API, timeout=10)
        filter_data = filter_resp.json().get("result", {})
        taxonomy_ids = [t["taxonomyId"] for t in filter_data.get("jobTaxonomyList", [])]
        print(f"[scraper] Filters: jobTypes={filter_data.get('jobTypes')} seniority={filter_data.get('seniority')} taxonomies={taxonomy_ids}")
    except Exception as e:
        print(f"[scraper] Could not fetch filter state: {e}")

    print("[scraper] Fetching filtered jobs...")
    job_list = []

    # Use the paginated list endpoint which respects saved filter state
    params = {
        "refresh": "true",
        "sortCondition": "1",  # 1 = Most Recent
        "position": "0",
        "count": "20",
        "syncRerank": "false",
    }
    try:
        resp = session.get(LIST_API, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        job_list = body.get("result", {}).get("jobList", [])
        print(f"[scraper] GET list/jobs → {len(job_list)} jobs")
    except Exception as e:
        print(f"[scraper] GET list/jobs failed: {e}")

    captured = _extract_items(job_list)

    seen_ids: set[str] = set()
    normalized: list[dict] = []
    for raw in captured:
        job = _normalize_job(raw)
        if job and job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            normalized.append(job)

    print(f"[scraper] Total jobs: {len(normalized)}")
    filtered = [j for j in normalized if _matches_filter(j)]
    print(f"[scraper] Matching filter: {len(filtered)}")

    if not filtered:
        print("[scraper] No matches — session may be expired or no matching jobs right now.")

    return filtered

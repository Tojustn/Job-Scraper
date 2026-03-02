import requests
from typing import Optional

import config

JOBS_API = "https://jobright.ai/swan/recommend/landing/jobs"
RECENT_API = "https://jobright.ai/swan/recent/landing/jobs"
FILTER_API = "https://jobright.ai/swan/filter/get/filter"

ROLE_KEYWORDS = [
    "full stack", "fullstack", "full-stack",
    "backend", "back end", "back-end",
    "python",
    "c++", "c/c++",
    "software engineer", "software developer", "swe",
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
    company = raw.get("companyName") or raw.get("company") or "Unknown Company"
    location = (
        raw.get("jobLocation")
        or raw.get("location")
        or ("Remote" if raw.get("isRemote") else "Unknown Location")
    )
    job_url = raw.get("url") or f"https://jobright.ai/jobs/info/{job_id}"
    match_score = raw.get("matchScore") or raw.get("score")
    return {
        "id": str(job_id),
        "title": title,
        "company": company,
        "location": location,
        "url": job_url,
        "matchScore": match_score,
    }


async def scrape_jobs() -> list[dict]:
    session = requests.Session()
    session.cookies.set("SESSION_ID", config.JOBRIGHT_SESSION_ID, domain="jobright.ai")
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "referer": "https://jobright.ai/jobs/recommend",
        "x-client-type": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    })

    # Get saved filter state to use as request params
    filter_data = {}
    try:
        filter_resp = session.post(FILTER_API, timeout=10)
        filter_data = filter_resp.json().get("result", {})
        taxonomy_ids = [t["taxonomyId"] for t in filter_data.get("jobTaxonomyList", [])]
        print(f"[scraper] Filters: jobTypes={filter_data.get('jobTypes')} seniority={filter_data.get('seniority')} taxonomies={taxonomy_ids}")
    except Exception as e:
        print(f"[scraper] Could not fetch filter state: {e}")

    print("[scraper] Fetching jobs from API with filters...")
    job_list = []

    # POST the exact filter state the UI uses
    try:
        resp = session.post(JOBS_API, json=filter_data, timeout=30)
        resp.raise_for_status()
        jobs = resp.json().get("result", {}).get("jobList", [])
        print(f"[scraper] POST with filter_data → {len(jobs)} jobs")
        if jobs:
            job_list = jobs
    except Exception as e:
        print(f"[scraper] POST with filter_data failed: {e}")

    # Fall back to plain GET
    if not job_list:
        try:
            resp = session.get(JOBS_API, timeout=30)
            resp.raise_for_status()
            job_list = resp.json().get("result", {}).get("jobList", [])
            print(f"[scraper] GET (unfiltered) → {len(job_list)} jobs")
        except Exception as e:
            print(f"[scraper] GET failed: {e}")

    # Print raw keys of first item to find company field
    if job_list:
        first = job_list[0]
        print(f"[scraper] Top-level item keys: {list(first.keys())}")
        if "jobResult" in first:
            print(f"[scraper] jobResult keys: {list(first['jobResult'].keys())}")
    print(f"[scraper] Got {len(job_list)} jobs from API")

    captured = []
    for item in job_list:
        job_result = item.get("jobResult", {})
        merged = {**item, **job_result}
        merged.pop("jobResult", None)
        captured.append(merged)

    seen_ids: set[str] = set()
    normalized: list[dict] = []
    for raw in captured:
        job = _normalize_job(raw)
        if job and job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            normalized.append(job)

    print(f"[scraper] Total jobs: {len(normalized)}")
    for r in captured:
        print(f"[scraper]   {r.get('jobTitle','?')} | {r.get('jobSeniority','?')} | {r.get('companyName','?')}")
    filtered = [j for j in normalized if _matches_filter(j)]
    print(f"[scraper] Matching internship+role filter: {len(filtered)}")

    if not filtered:
        print("[scraper] No matches. Session may have expired or no internship roles in current recommendations.")

    return filtered

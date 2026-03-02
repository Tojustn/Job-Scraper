import asyncio
import json
from typing import Optional

from playwright.async_api import async_playwright, Response, Page

import config


def _is_job_like(obj: dict) -> bool:
    """Heuristic: an object looks like a job if it has id + title + company fields."""
    return (
        isinstance(obj, dict)
        and any(k in obj for k in ("id", "jobId", "job_id"))
        and any(k in obj for k in ("title", "jobTitle", "job_title", "position"))
        and any(k in obj for k in ("company", "companyName", "company_name", "employer"))
    )


def _extract_jobs_from_payload(payload) -> list[dict]:
    """Recursively search a parsed JSON payload for arrays of job-like objects."""
    jobs = []
    if isinstance(payload, list):
        if all(_is_job_like(item) for item in payload) and payload:
            jobs.extend(payload)
        else:
            for item in payload:
                jobs.extend(_extract_jobs_from_payload(item))
    elif isinstance(payload, dict):
        for value in payload.values():
            jobs.extend(_extract_jobs_from_payload(value))
    return jobs


def _normalize_job(raw: dict) -> Optional[dict]:
    """Normalize a raw job dict into a consistent schema."""
    job_id = raw.get("jobId") or raw.get("id") or raw.get("job_id")
    if not job_id:
        return None

    title = (
        raw.get("jobTitle")
        or raw.get("title")
        or raw.get("job_title")
        or raw.get("position")
        or "Unknown Title"
    )
    company = (
        raw.get("companyName")
        or raw.get("company")
        or raw.get("company_name")
        or raw.get("employerName")
        or raw.get("employer")
        or "Unknown Company"
    )
    location = (
        raw.get("jobLocation")
        or raw.get("location")
        or raw.get("city")
        or ("Remote" if raw.get("isRemote") else "Unknown Location")
    )

    job_url = (
        raw.get("url")
        or raw.get("jobUrl")
        or raw.get("link")
        or f"https://jobright.ai/jobs/info/{job_id}"
    )

    match_score = raw.get("matchScore") or raw.get("match_score") or raw.get("score")

    return {
        "id": str(job_id),
        "title": title,
        "company": company,
        "location": location,
        "url": job_url,
        "matchScore": match_score,
    }


async def _handle_login(page: Page) -> None:
    """Fill and submit the email/password login form."""
    print("[scraper] Session expired or not logged in — attempting login...")
    try:
        await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10_000)
        await page.fill('input[type="email"], input[name="email"]', config.JOBRIGHT_EMAIL)
        await page.fill('input[type="password"], input[name="password"]', config.JOBRIGHT_PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle", timeout=30_000)
        print("[scraper] Login submitted, waiting for navigation...")
    except Exception as e:
        print(f"[scraper] Login attempt failed: {e}")
        print("[scraper] If you use Google/LinkedIn SSO, run `python login.py` once to save your session.")


async def scrape_jobs() -> list[dict]:
    """
    Open the JobRight jobs page using a persistent browser context, intercept API
    responses, and return a deduplicated list of normalized job dicts.
    """
    captured_jobs: list[dict] = []

    async def on_response(response: Response) -> None:
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return
        try:
            body = await response.json()
            # Directly extract from the known JobRight jobs endpoint
            if "recommend/landing/jobs" in response.url or "recent/landing/jobs" in response.url:
                job_list = body.get("result", {}).get("jobList", [])
                for item in job_list:
                    job_result = item.get("jobResult", item)
                    captured_jobs.append(job_result)
                print(f"[scraper] Intercepted {len(job_list)} job(s) from {response.url}")
        except Exception:
            pass  # Not valid JSON or parse error — skip silently

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_DATA_DIR,
            headless=config.HEADLESS,
            args=["--no-sandbox"],
        )

        page = context.pages[0] if context.pages else await context.new_page()
        page.on("response", on_response)

        print(f"[scraper] Navigating to {config.JOBS_URL}...")
        await page.goto(config.JOBS_URL, wait_until="domcontentloaded", timeout=60_000)
        # Wait for initial API calls to fire
        await asyncio.sleep(5)

        # Detect redirect to login page — check for login-specific indicators,
        # not URL path (SPA shell always loads at / before client-side routing)
        current_url = page.url
        print(f"[scraper] Landed on: {current_url}")
        is_login_page = await page.locator('input[type="password"]').count() > 0
        if is_login_page:
            print("[scraper] Login page detected — attempting login...")
            await _handle_login(page)
            await page.goto(config.JOBS_URL, wait_until="domcontentloaded", timeout=60_000)
            await asyncio.sleep(5)
            print(f"[scraper] After login, landed on: {page.url}")

        # Click "Most Recent" tab to get chronological results
        try:
            await page.get_by_text("Most Recent", exact=True).first.click()
            print("[scraper] Clicked 'Most Recent' tab.")
            await asyncio.sleep(3)
        except Exception:
            print("[scraper] Could not find 'Most Recent' tab — using default tab.")

        # Brief pause + scroll to trigger lazy-loaded content
        await asyncio.sleep(3)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        # Scroll back up to catch any top-loaded content as well
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)

        await context.close()

    # Normalize and deduplicate by job ID
    seen_ids: set[str] = set()
    normalized: list[dict] = []
    for raw in captured_jobs:
        job = _normalize_job(raw)
        if job and job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            normalized.append(job)

    if not normalized:
        print(
            "[scraper] WARNING: No jobs were intercepted. "
            "The API structure may have changed — inspect network traffic manually."
        )
    else:
        print(f"[scraper] Total unique jobs found: {len(normalized)}")

    return normalized

import asyncio
import json
from typing import Optional

from playwright.async_api import async_playwright, Response, Page

import config

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


async def _apply_filters(page: Page) -> None:
    """Try to apply Job Type: Internship filter on the page."""
    try:
        # Look for a "Job Type" filter button and click it
        job_type_btn = page.get_by_text("Job Type", exact=False).first
        await job_type_btn.click(timeout=10_000)
        await asyncio.sleep(1)

        # Click "Internship" option
        await page.get_by_text("Internship", exact=True).first.click(timeout=10_000)
        await asyncio.sleep(5)
        print("[scraper] Applied Job Type: Internship filter.")
    except Exception as e:
        print(f"[scraper] Could not apply Job Type filter: {e}")

    try:
        # Look for "Job Function" filter
        job_fn_btn = page.get_by_text("Job Function", exact=False).first
        await job_fn_btn.click(timeout=10_000)
        await asyncio.sleep(1)

        for label in ["Full Stack Engineer", "Backend Engineer", "Python Engineer", "C/C++ Engineer"]:
            try:
                await page.get_by_text(label, exact=True).first.click(timeout=3_000)
                await asyncio.sleep(0.5)
                print(f"[scraper] Selected job function: {label}")
            except Exception:
                print(f"[scraper] Could not find job function option: {label}")

        # Close the dropdown by pressing Escape
        await page.keyboard.press("Escape")
        await asyncio.sleep(3)
    except Exception as e:
        print(f"[scraper] Could not apply Job Function filter: {e}")


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
                    job_result = item.get("jobResult", {})
                    # Merge parent item fields (contains companyName etc.) with jobResult
                    merged = {**item, **job_result}
                    merged.pop("jobResult", None)
                    captured_jobs.append(merged)
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

        # Log all POST/PUT requests to jobright API so we can learn the filter format
        async def on_request(request):
            if "jobright.ai/swan" in request.url and request.method in ("POST", "PUT"):
                try:
                    body = request.post_data
                    print(f"[scraper] REQUEST {request.method} {request.url} body={body}")
                except Exception:
                    pass
        page.on("request", on_request)

        # Always log in explicitly — GitHub Actions has no saved session
        print("[scraper] Navigating to login page...")
        await page.goto("https://jobright.ai/login", wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(3)

        if await page.locator('input[type="password"]').count() > 0:
            await _handle_login(page)
        else:
            print("[scraper] Already authenticated, skipping login.")

        # Now navigate to jobs page and wait for React to fully render
        print(f"[scraper] Navigating to {config.JOBS_URL}...")
        await page.goto(config.JOBS_URL, wait_until="domcontentloaded", timeout=60_000)
        print("[scraper] Waiting for page to render...")
        await asyncio.sleep(15)

        # Take a screenshot so we can see what the page looks like
        await page.screenshot(path="debug_screenshot.png", full_page=False)
        print(f"[scraper] Screenshot saved. Current URL: {page.url}")

        # Log all visible button text to find the right filter selectors
        buttons = await page.locator("button").all_text_contents()
        print(f"[scraper] Visible buttons: {buttons[:20]}")

        # Clear jobs captured during initial load — we want only the filtered results
        captured_jobs.clear()

        # Apply filters and wait for the filtered API response
        await _apply_filters(page)

        # Scroll to trigger lazy-loaded content
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

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
        return normalized

    print(f"[scraper] Total jobs before filter: {len(normalized)}")
    filtered = [j for j in normalized if _matches_filter(j)]
    print(f"[scraper] Jobs matching filter (internship + role): {len(filtered)}")
    return filtered

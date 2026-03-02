import asyncio
import sys

import config
from scraper import scrape_jobs
from notifier import send_discord_notification
from storage import load_seen_jobs, save_seen_jobs


async def run_once(seen: set) -> set:
    """Run a single scrape cycle. Returns the updated seen set."""
    jobs = await scrape_jobs()
    new_jobs = [j for j in jobs if j["id"] not in seen]

    if new_jobs:
        print(f"[main] {len(new_jobs)} new job(s) found — sending notifications...")
        for job in new_jobs:
            send_discord_notification(job)
            seen.add(job["id"])
    else:
        print("[main] No new jobs since last check.")

    save_seen_jobs(seen)
    return seen


async def main(once: bool = False) -> None:
    print("[main] JobRight Scraper starting...")
    print(f"[main] Jobs URL: {config.JOBS_URL}")

    seen = load_seen_jobs()
    print(f"[main] Loaded {len(seen)} previously seen job ID(s).")

    if once:
        print("[main] Running single scrape cycle (--once mode)...")
        await run_once(seen)
        return

    print(f"[main] Checking every {config.CHECK_INTERVAL_MINUTES} minute(s).")
    while True:
        print("\n[main] Starting scrape...")
        try:
            seen = await run_once(seen)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[main] Error during scrape: {e}")

        print(f"[main] Sleeping {config.CHECK_INTERVAL_MINUTES} minute(s) until next check...")
        await asyncio.sleep(config.CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    once_mode = "--once" in sys.argv
    try:
        asyncio.run(main(once=once_mode))
    except KeyboardInterrupt:
        print("\n[main] Stopped by user.")
        sys.exit(0)

import json
import os

SEEN_JOBS_FILE = "seen_jobs.json"


def load_seen_jobs() -> set:
    if not os.path.exists(SEEN_JOBS_FILE):
        return set()
    try:
        with open(SEEN_JOBS_FILE, "r") as f:
            data = json.load(f)
            return set(data)
    except (json.JSONDecodeError, ValueError):
        print(f"[storage] Warning: {SEEN_JOBS_FILE} was corrupt, starting fresh.")
        return set()


def save_seen_jobs(seen: set) -> None:
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)

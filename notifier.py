import time
import requests
from config import DISCORD_WEBHOOK_URL


def send_discord_notification(job: dict) -> None:
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Unknown Location")
    url = job.get("url", "")
    match_score = job.get("matchScore")

    description_parts = [f"**Company:** {company}", f"**Location:** {location}"]
    if match_score is not None:
        description_parts.append(f"**Match Score:** {match_score}%")

    embed = {
        "title": title,
        "url": url if url else None,
        "description": "\n".join(description_parts),
        "color": 0x5865F2,  # Discord blurple
        "footer": {"text": "JobRight Scraper"},
    }

    embed = {k: v for k, v in embed.items() if v is not None}
    payload = {"embeds": [embed]}

    for attempt in range(3):
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 2)
                print(f"[notifier] Rate limited — waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            print(f"[notifier] Sent: {title} @ {company}")
            time.sleep(1)  # Stay well under Discord's rate limit
            return
        except requests.RequestException as e:
            print(f"[notifier] Failed to send Discord notification: {e}")
            return

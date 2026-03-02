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

    # Remove None values from embed
    embed = {k: v for k, v in embed.items() if v is not None}

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[notifier] Sent: {title} @ {company}")
    except requests.RequestException as e:
        print(f"[notifier] Failed to send Discord notification: {e}")

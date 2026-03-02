import time
import requests
from config import DISCORD_WEBHOOK_URL


def send_discord_notification(job: dict) -> None:
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Unknown Location")
    url = job.get("url", "")
    salary = job.get("salary")
    posted_at = job.get("postedAt")
    work_model = job.get("workModel")
    match_score = job.get("matchScore")

    fields = [
        {"name": "Company", "value": company, "inline": True},
        {"name": "Location", "value": location, "inline": True},
    ]
    if work_model:
        fields.append({"name": "Work Model", "value": work_model, "inline": True})
    if salary:
        fields.append({"name": "Pay", "value": salary, "inline": True})
    if match_score is not None:
        fields.append({"name": "Match Score", "value": f"{match_score}%", "inline": True})

    footer_text = "JobRight Scraper"
    if posted_at:
        footer_text += f" • Posted {posted_at}"

    embed = {
        "title": title,
        "url": url or None,
        "color": 0x57F287,  # Green
        "fields": fields,
        "footer": {"text": footer_text},
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

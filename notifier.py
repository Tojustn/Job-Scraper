import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from config import DISCORD_WEBHOOK_URL, GMAIL_APP_PASSWORD, NOTIFY_EMAIL


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


def send_email_notification(job: dict) -> None:
    if not GMAIL_APP_PASSWORD:
        return

    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Unknown Location")
    url = job.get("url", "")
    salary = job.get("salary", "")
    work_model = job.get("workModel", "")
    posted_at = job.get("postedAt", "")

    rows = f"""
        <tr><td><b>Company</b></td><td>{company}</td></tr>
        <tr><td><b>Location</b></td><td>{location}</td></tr>
    """
    if work_model:
        rows += f"<tr><td><b>Work Model</b></td><td>{work_model}</td></tr>"
    if salary:
        rows += f"<tr><td><b>Pay</b></td><td>{salary}</td></tr>"
    if posted_at:
        rows += f"<tr><td><b>Posted</b></td><td>{posted_at}</td></tr>"

    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto">
      <h2 style="color:#2d7d46">New Internship: {title}</h2>
      <table cellpadding="8" style="border-collapse:collapse;width:100%">
        {rows}
      </table>
      <br>
      <a href="{url}" style="background:#2d7d46;color:white;padding:10px 20px;
         text-decoration:none;border-radius:5px;display:inline-block">
        View &amp; Apply
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">JobRight Scraper</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"New Internship: {title} @ {company}"
    msg["From"] = NOTIFY_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(NOTIFY_EMAIL, GMAIL_APP_PASSWORD)
            smtp.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"[notifier] Email sent: {title} @ {company}")
    except Exception as e:
        print(f"[notifier] Email failed: {e}")

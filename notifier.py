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


def send_email_digest(jobs: list) -> None:
    if not GMAIL_APP_PASSWORD or not jobs:
        return

    def job_card(job: dict) -> str:
        title = job.get("title", "Unknown Title")
        company = job.get("company", "Unknown Company")
        location = job.get("location", "Unknown Location")
        url = job.get("url", "")
        salary = job.get("salary", "")
        work_model = job.get("workModel", "")
        posted_at = job.get("postedAt", "")
        logo = job.get("logo", "")

        logo_html = (
            f'<img src="{logo}" alt="{company}" '
            f'style="width:48px;height:48px;object-fit:contain;border-radius:8px;margin-right:12px">'
            if logo else
            f'<div style="width:48px;height:48px;background:#e8f5e9;border-radius:8px;'
            f'margin-right:12px;display:flex;align-items:center;justify-content:center;'
            f'font-size:20px">🏢</div>'
        )

        meta = " · ".join(filter(None, [location, work_model, salary, posted_at]))

        return f"""
        <div style="border:1px solid #e0e0e0;border-radius:10px;padding:16px;margin-bottom:16px">
          <div style="display:flex;align-items:center;margin-bottom:10px">
            {logo_html}
            <div>
              <div style="font-size:16px;font-weight:bold">{title}</div>
              <div style="color:#555;font-size:14px">{company}</div>
            </div>
          </div>
          <div style="color:#777;font-size:13px;margin-bottom:12px">{meta}</div>
          <a href="{url}" style="background:#2d7d46;color:white;padding:8px 16px;
             text-decoration:none;border-radius:6px;font-size:13px;display:inline-block">
            View &amp; Apply
          </a>
        </div>
        """

    cards = "".join(job_card(j) for j in jobs)
    count = len(jobs)
    subject = f"{count} New Internship{'s' if count > 1 else ''} on JobRight"

    html = f"""
    <html><body style="font-family:sans-serif;max-width:620px;margin:auto;padding:20px">
      <h2 style="color:#2d7d46;margin-bottom:4px">{subject}</h2>
      <p style="color:#888;font-size:13px;margin-top:0;margin-bottom:20px">
        Matching your filters on JobRight AI
      </p>
      {cards}
      <p style="color:#aaa;font-size:11px;margin-top:24px;text-align:center">
        JobRight Scraper · Checks every 30 minutes
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = NOTIFY_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(NOTIFY_EMAIL, GMAIL_APP_PASSWORD)
            smtp.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"[notifier] Email digest sent: {count} job(s)")
    except Exception as e:
        print(f"[notifier] Email failed: {e}")

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}. Check your .env file.")
    return value


def _optional(key: str, default: str) -> str:
    return os.getenv(key, default)


JOBRIGHT_EMAIL: str = _optional("JOBRIGHT_EMAIL", "")
JOBRIGHT_PASSWORD: str = _optional("JOBRIGHT_PASSWORD", "")
JOBRIGHT_SESSION_ID: str = _require("JOBRIGHT_SESSION_ID")
DISCORD_WEBHOOK_URL: str = _require("DISCORD_WEBHOOK_URL")
GMAIL_APP_PASSWORD: str = _optional("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL: str = _optional("NOTIFY_EMAIL", "justin.to.contact@gmail.com")
JOBS_URL: str = _optional("JOBS_URL", "https://jobright.ai/jobs")
CHECK_INTERVAL_MINUTES: int = int(_optional("CHECK_INTERVAL_MINUTES", "30"))

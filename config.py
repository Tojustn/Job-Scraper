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


JOBRIGHT_EMAIL: str = _require("JOBRIGHT_EMAIL")
JOBRIGHT_PASSWORD: str = _require("JOBRIGHT_PASSWORD")
DISCORD_WEBHOOK_URL: str = _require("DISCORD_WEBHOOK_URL")
JOBS_URL: str = _optional("JOBS_URL", "https://jobright.ai/jobs")
CHECK_INTERVAL_MINUTES: int = int(_optional("CHECK_INTERVAL_MINUTES", "30"))
HEADLESS: bool = _optional("HEADLESS", "true").lower() == "true"
BROWSER_DATA_DIR: str = _optional("BROWSER_DATA_DIR", "./browser_data")

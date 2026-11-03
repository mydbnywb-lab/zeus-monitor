import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")

MINI_APP_DOMAIN = os.getenv("MINI_APP_DOMAIN", "")

PANEL_URL = os.getenv("PANEL_URL", "").rstrip("/")
PANEL_API_KEY = os.getenv("PANEL_API_KEY", "")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{BASE_DIR}/database/zeus.db"
)

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate_settings():
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not configured.")

    if not ADMIN_ID.isdigit():
        errors.append("ADMIN_ID must be a numeric Telegram ID.")

    if not PANEL_URL:
        errors.append("PANEL_URL is not configured.")

    if not PANEL_API_KEY:
        errors.append("PANEL_API_KEY is not configured.")

    if CHECK_INTERVAL < 10:
        errors.append("CHECK_INTERVAL must be at least 10 seconds.")

    return errors

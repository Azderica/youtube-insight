import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def db_path() -> Path:
    override = os.environ.get("YOUTUBE_INSIGHT_DB")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "youtube_insight.db"


def notify_url() -> str:
    return os.environ.get("NOTIFY_URL", "http://localhost:8080/internal/notify")


def internal_api_token() -> str:
    return os.environ.get("INTERNAL_API_TOKEN", "")


def notion_token() -> str:
    return os.environ.get("NOTION_TOKEN", "")


def notion_database_id() -> str:
    return os.environ.get("NOTION_DATABASE_ID", "")


def google_client_secret_path() -> Path:
    override = os.environ.get("GOOGLE_CLIENT_SECRET_PATH")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "client_secret.json"


def google_token_path() -> Path:
    override = os.environ.get("GOOGLE_TOKEN_PATH")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data" / "google_token.json"

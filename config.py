"""Configuration for the Digital Adjudicator Flask application."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _normalised_db_url() -> str:
    """Return the DATABASE_URL, fixing the postgres:// prefix that Render gives.

    SQLAlchemy 2.x requires `postgresql://` (or `postgresql+psycopg2://`),
    but Render and some other providers still use the legacy `postgres://`.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url:
        return url
    return f"sqlite:///{BASE_DIR / 'instance' / 'adjudicator.db'}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-please-and-thank-you")
    SQLALCHEMY_DATABASE_URI = _normalised_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    WTF_CSRF_ENABLED = True

    # Session
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours

    # SocketIO
    SOCKETIO_ASYNC_MODE = "threading"

    # File uploads (profile photos, etc.)
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https"

    def __init__(self):
        # In production, fail loudly if SECRET_KEY isn't set
        if self.SECRET_KEY == "change-me-in-production-please-and-thank-you":
            print(
                "WARNING: SECRET_KEY is using the default value. "
                "Set the SECRET_KEY environment variable in production.",
                file=sys.stderr,
            )

import os
import time

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Cache-busts static JS/CSS on every process start (including Flask's
    # debug-reloader restarts), so editing player.js during dev doesn't
    # leave the browser running a stale cached copy.
    ASSET_VERSION = int(time.time())

    # Never hardcode this in production — Render injects it as an env var.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Render's Postgres gives postgres:// but SQLAlchemy 1.4+ wants postgresql://
    _db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'gym_tracker.db')}")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Reject anything over 10MB before it even hits the parser.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Session cookie hardening.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    REMEMBER_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # Set this to use Claude-based extraction; otherwise the regex parser is used.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

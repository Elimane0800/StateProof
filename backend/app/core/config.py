"""Runtime configuration. Reads from environment / .env, never from git."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_db_url(url: str) -> str:
    """Force Postgres URLs onto the psycopg v3 driver.

    SQLAlchemy defaults a bare ``postgresql://`` (and ``postgresql+psycopg2://``)
    to psycopg2, which we avoid on Windows. Rewriting the scheme to
    ``postgresql+psycopg://`` selects psycopg v3 regardless of the env value.
    """
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):  # some providers emit this legacy scheme
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


class Settings:
    """Environment-driven settings. Instantiated once via get_settings()."""

    def __init__(self) -> None:
        # VLM providers. Two configured (Gemini + a fallback) per the risk table.
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # When no key is present (or MOCK_MODE=1), the service serves the mock
        # payload so R4/R5 are never blocked on R1.
        self.mock_mode: bool = _get_bool("MOCK_MODE", default=not self._any_key())

        # Storage + assets.
        self.data_dir: Path = Path(os.getenv("DATA_DIR", str(BACKEND_ROOT / "var" / "audits")))
        self.artifacts_dir: Path = Path(
            os.getenv("ARTIFACTS_DIR", str(BACKEND_ROOT / "var" / "artifacts"))
        )
        self.mock_path: Path = BACKEND_ROOT / "mocks" / "audit_mock.json"

        # Rental registry: SQL database + uploaded videos.
        # DATABASE_URL unset -> local SQLite file (zero external setup). A bare
        # postgresql:// value is normalized to the psycopg v3 driver below.
        self.database_url: str = _normalize_db_url(
            os.getenv("DATABASE_URL", f"sqlite:///{(BACKEND_ROOT / 'var' / 'registry.db')}")
        )
        self.uploads_dir: Path = Path(
            os.getenv("UPLOADS_DIR", str(BACKEND_ROOT / "var" / "uploads"))
        )
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "200"))
        self.allowed_video_ext: set[str] = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in os.getenv("ALLOWED_VIDEO_EXT", ".mp4,.mov,.webm").split(",")
            if ext.strip()
        }

        # The public base URL of the Studio, used to build report links in comments.
        self.studio_base_url: str = os.getenv("STUDIO_BASE_URL", "http://localhost:5173")

        # VLM call budget.
        self.request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "45"))
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "2"))

        # CORS origins for the Studio dev server.
        self.cors_origins: list[str] = os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")

    def _any_key(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

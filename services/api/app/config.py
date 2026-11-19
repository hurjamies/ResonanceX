"""Runtime configuration for the ResonanceX API.

All settings can be overridden with environment variables prefixed ``RESONANCEX_``
(see ``.env.example`` in the repository root).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESONANCEX_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    database_url: str | None = None
    max_upload_mb: int = 300
    max_duration_seconds: float = 60 * 30
    analysis_workers: int = 1
    # Only bind locally by default; the app is not meant to be exposed publicly.
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Serve the built frontend (apps/web/dist) from the API when present.
    serve_frontend: bool = True
    # Run analysis jobs inline (used by tests).
    synchronous_jobs: bool = False

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def analysis_dir(self) -> Path:
        return self.data_dir / "analysis"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'resonancex.db'}"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.analysis_dir, self.exports_dir, self.generated_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

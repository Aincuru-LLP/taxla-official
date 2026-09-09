import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


def _parse_cors_origins(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database — SQLite is the MVP default. To use Postgres, override DATABASE_URL
    # and SYNC_DATABASE_URL in your .env (see .env.example).
    DATABASE_URL: str = "sqlite+aiosqlite:///./taxla.db"
    SYNC_DATABASE_URL: str = "sqlite:///./taxla.db"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security — JWT_SECRET has no default. It must be set via env (.env in dev,
    # real env var in staging/prod). Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
    JWT_SECRET: str = Field(default=None)  # type: ignore[assignment]
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Cookie attributes for the refresh token. ``Secure`` is HTTPS-only;
    # the default below is auto-set from ENVIRONMENT so plain-HTTP dev works
    # out of the box (browsers silently drop Secure cookies on http://
    # requests, which would otherwise produce a login → 401-refresh loop).
    # Override explicitly: set COOKIE_SECURE=true in prod.
    COOKIE_SECURE: bool | None = None
    COOKIE_SAMESITE: str = "lax"  # "strict" breaks OAuth/SSO redirects; "lax" is the safe default
    REFRESH_COOKIE_NAME: str = "taxla_refresh"

    # CORS — explicit allow-list from env (comma-separated). Browsers reject
    # `allow_origins=["*"]` combined with `allow_credentials=True`, so we require
    # an explicit list. In dev, http://localhost:3000 is the default.
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000"

    # Local AI
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    # OCR provider selection. Default 'tesseract' is the cross-platform default.
    # Phase 02 follow-up: provider is swappable via env so we can swap in
    # PaddleOCR (Linux-only) without touching the worker.
    OCR_PROVIDER: str = "tesseract"

    # File Storage
    STORAGE_DIR: str = "./storage"
    DOCUMENTS_DIR: str = "./storage/documents"
    CERTIFICATES_DIR: str = "./storage/certificates"
    DEBUG_SCREENSHOTS_DIR: str = "./storage/debug"
    UDYAM_PORTAL_URL: str = "https://udyamregistration.gov.in/"
    UDYAM_TARGET_URL: str = os.environ.get("UDYAM_TARGET_URL", "https://msme-form.vercel.app/udyam")

    # Phase 09 — Portal automation mode selector.
    #   MOCK : tests/fixtures/mock_portal/ (selected by ``portal_selectors.get_selectors``)
    #   LIVE : the real udyamregistration.gov.in portal or configurable target
    PORTAL_MODE: str = "MOCK"
    # Resolved at runtime by portal_selectors.get_selectors. Empty by default
    # so MOCK mode picks up the test fixture URL passed in by the test.
    PORTAL_BASE_URL: str = ""

    @property
    def cors_allow_origins(self) -> List[str]:
        return _parse_cors_origins(self.CORS_ALLOW_ORIGINS)

    @property
    def refresh_cookie_secure(self) -> bool:
        """Resolve ``COOKIE_SECURE`` for the current environment.

        - None / unset: auto — ``False`` in development (plain HTTP), ``True``
          everywhere else (HTTPS required).
        - Explicit value (``true`` / ``false``) wins, so prod .env can lock
          this down regardless of ENVIRONMENT.
        """
        if self.COOKIE_SECURE is None:
            return self.ENVIRONMENT != "development"
        return self.COOKIE_SECURE

    def validate_for_environment(self) -> None:
        """Fail fast on missing/insecure configuration. Call from app startup."""
        if not self.JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET is not set. Add it to your .env (see .env.example) or "
                "export JWT_SECRET=<value>. Generate one with `python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\"`."
            )
        if self.ENVIRONMENT != "development" and self.JWT_SECRET.startswith("change_me"):
            raise RuntimeError(
                "JWT_SECRET still uses the placeholder. Regenerate for non-dev."
            )


settings = Settings()

# Ensure directories exist
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
os.makedirs(settings.CERTIFICATES_DIR, exist_ok=True)
os.makedirs(settings.DEBUG_SCREENSHOTS_DIR, exist_ok=True)
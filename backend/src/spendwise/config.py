"""All settings come from environment variables (or a .env file), never from the code.

The same code then runs on your laptop (SQLite, no AI key) and in production (PostgreSQL, a real
secret, a Groq key) by changing only the environment. That's the twelve-factor way.
"""

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("spendwise")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"  # dev | prod
    database_url: str = "sqlite:///./spendwise.db"  # prod: postgresql+psycopg://user:pass@host/db
    jwt_secret: str = ""  # REQUIRED in prod (see get_settings)
    jwt_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    groq_api_key: str = ""
    groq_api_key_file: str = ""  # or a path to a file holding the key
    ai_model: str = "openai/gpt-oss-120b"
    ai_calls_per_hour: int = 40  # per user: protects the free API quota
    ai_calls_per_day: int = 2000  # for the whole server: sign-ups are open, the quota is shared

    timezone: str = "Asia/Kolkata"  # "today" for the users; servers usually run on UTC
    max_upload_mb: float = 2.0
    max_import_rows: int = 20_000

    def groq_key(self) -> str:
        if self.groq_api_key.strip():
            return self.groq_api_key.strip()
        if self.groq_api_key_file and Path(self.groq_api_key_file).is_file():
            return Path(self.groq_api_key_file).read_text(encoding="utf-8").strip()
        return ""


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.environment == "prod" and len(s.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a random value of 32+ characters in production "
            '(e.g. python -c "import secrets; print(secrets.token_urlsafe(48))")'
        )
    if not s.jwt_secret:
        # dev only: a random secret per run, so nobody ships a known default. Logins end on restart.
        s.jwt_secret = secrets.token_urlsafe(48)
        log.warning("JWT_SECRET is not set: using a random one for this run (dev only)")
    return s

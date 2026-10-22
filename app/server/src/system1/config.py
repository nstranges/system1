from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> system1 -> src -> server -> app -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]

_SQLITE_PREFIX = "sqlite:///"


class Settings(BaseSettings):
    # The .env path is absolute so settings don't depend on the working directory.
    # A missing file is fine: deployed config comes from environment variables.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    typesafe_api_key: str | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    jev_model: str = "jev-1.13.0"

    clerk_secret_key: str | None = None
    # Browser origins allowed by CORS (and, with clerk_enforce_azp, by the token's azp claim).
    client_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # We authenticate with a Bearer header, not an ambient cookie, so azp is defence in depth. Enable in production.
    clerk_enforce_azp: bool = False

    database_url: str = "sqlite:///app/server/.data/system1.db"

    llm_provider: Literal["anthropic", "fake"] = "anthropic"
    jev_provider: Literal["typesafe", "fake"] = "typesafe"
    sys1_provider: Literal["none", "http", "fake"] = "none"
    sys1_base_url: str | None = None
    sys1_model: str = "sys1"
    trainer: Literal["none", "fake", "preview"] = "preview"

    agent_model: str = "claude-sonnet-5-5"
    agent_effort: str = "medium"

    org_daily_token_cap: int = 3_000_000
    max_input_chars: int = 6000
    auto_threshold: float = 0.8
    est_cost_per_example_usd: float = 0.02

    playbook_path: str = ".claude/skills/system1-onboard/playbook.md"
    static_dir: str | None = None

    @field_validator("database_url")
    @classmethod
    def _resolve_sqlite_path(cls, v: str) -> str:
        # Relative sqlite paths are relative to the repo root; absolute ones (sqlite:////...) pass through.
        if v.startswith(_SQLITE_PREFIX):
            path = v.removeprefix(_SQLITE_PREFIX)
            if path and path != ":memory:" and not Path(path).is_absolute():
                return f"{_SQLITE_PREFIX}{REPO_ROOT / path}"
        return v

    @field_validator("playbook_path", "static_dir")
    @classmethod
    def _resolve_path(cls, v: str | None) -> str | None:
        if v is None or Path(v).is_absolute():
            return v
        return str(REPO_ROOT / v)


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""FastAPI runtime configuration (separate from the ML YAML config).

The ML pipeline reads its own YAML files (see ``configs/``); this object is
just for HTTP serving knobs and the path to the YAML to load at startup.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    roomos_config: str = "configs/inference.yaml"
    roomos_actions_config: str = "configs/actions.yaml"
    roomos_autostart: bool = True  # auto-start live engine on app startup (override via .env)
    roomos_log_level: str = "INFO"

    # Demo replay: off | replay | demo | demo-replay (see docs/DEMO-REPLAY.md)
    roomos_demo_mode: str = "off"
    roomos_demo_fixture: str = "configs/demo_replay.json"

    # CORS — your Next.js dev server.
    cors_allow_origins: list[str] = [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    # Telegram + OpenAI (see docs/TELEGRAM.md)
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    @field_validator("telegram_enabled", mode="before")
    @classmethod
    def _coerce_telegram_enabled(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return False


settings = Settings()

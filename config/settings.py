"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe paper-trading defaults."""

    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///quant_trading.db")
    live_trading_enabled: bool = _as_bool(
        os.getenv("LIVE_TRADING_ENABLED"), default=False
    )


settings = Settings()

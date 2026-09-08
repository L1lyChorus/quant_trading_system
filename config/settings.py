"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_decimal(value: Optional[str], default: Decimal) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("COMMISSION_RATE must be a decimal") from exc


def _as_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("freshness thresholds must be integers") from exc


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe paper-trading defaults."""

    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///quant_trading.db")
    commission_rate: Decimal = _as_decimal(
        os.getenv("COMMISSION_RATE"), Decimal("0.001")
    )
    max_trade_amount: Decimal = _as_decimal(
        os.getenv("MAX_TRADE_AMOUNT"), Decimal("1000")
    )
    max_total_position_ratio: Decimal = _as_decimal(
        os.getenv("MAX_TOTAL_POSITION_RATIO"), Decimal("0.80")
    )
    max_single_position_ratio: Decimal = _as_decimal(
        os.getenv("MAX_SINGLE_POSITION_RATIO"), Decimal("0.50")
    )
    news_fresh_threshold_seconds: int = _as_int(
        os.getenv("NEWS_FRESH_THRESHOLD_SECONDS"), 3600
    )
    news_stale_threshold_seconds: int = _as_int(
        os.getenv("NEWS_STALE_THRESHOLD_SECONDS"), 86400
    )
    market_fresh_threshold_seconds: int = _as_int(
        os.getenv("MARKET_FRESH_THRESHOLD_SECONDS"), 300
    )
    market_stale_threshold_seconds: int = _as_int(
        os.getenv("MARKET_STALE_THRESHOLD_SECONDS"), 86400
    )
    news_refresh_interval_minutes: int = _as_int(
        os.getenv("NEWS_REFRESH_INTERVAL_MINUTES"), 15
    )
    live_trading_enabled: bool = _as_bool(
        os.getenv("LIVE_TRADING_ENABLED"), default=False
    )


settings = Settings()

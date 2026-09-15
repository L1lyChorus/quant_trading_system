"""Freshness and health checks for market data sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from config.settings import settings


class FreshnessStatus(str, Enum):
    LATEST_AVAILABLE = "LATEST_AVAILABLE"
    DELAYED = "DELAYED"
    FRESH = "FRESH"
    STALE = "STALE"
    OUTDATED = "OUTDATED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class MarketHealthResult:
    availability: str
    freshness: FreshnessStatus
    latest_timestamp: Optional[datetime]
    fetched_at: datetime
    data_age: Optional[float]
    error: Optional[str]
    quote: Optional[object] = None


def assess_market_freshness(
    latest_timestamp: Optional[datetime],
    fetched_at: datetime,
    fresh_seconds: int = settings.market_fresh_threshold_seconds,
    stale_seconds: int = settings.market_stale_threshold_seconds,
):
    if latest_timestamp is None:
        return FreshnessStatus.UNKNOWN, None
    age = max(0.0, (fetched_at - latest_timestamp).total_seconds())
    if age <= fresh_seconds:
        status = FreshnessStatus.FRESH
    elif age <= stale_seconds:
        status = FreshnessStatus.STALE
    else:
        status = FreshnessStatus.OUTDATED
    return status, age

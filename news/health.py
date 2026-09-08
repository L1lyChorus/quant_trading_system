"""Freshness and health checks for news providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from config.settings import settings
from news.models import NewsItemDTO
from news.providers import NewsProvider, NewsProviderError


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    OUTDATED = "OUTDATED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class NewsHealthResult:
    availability: str
    freshness: FreshnessStatus
    latest_timestamp: Optional[datetime]
    fetched_at: datetime
    data_age: Optional[float]
    error: Optional[str]
    items: tuple = ()


def freshness_for(
    latest_timestamp: Optional[datetime],
    fetched_at: datetime,
    fresh_seconds: int,
    stale_seconds: int,
) -> tuple:
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


def check_news_provider_health(provider: NewsProvider) -> NewsHealthResult:
    fetched_at = datetime.now(timezone.utc)
    try:
        items = tuple(provider.fetch())
        latest = max(
            (item.published_at for item in items if item.published_at is not None),
            default=None,
        )
        status, age = freshness_for(
            latest,
            fetched_at,
            settings.news_fresh_threshold_seconds,
            settings.news_stale_threshold_seconds,
        )
        return NewsHealthResult("AVAILABLE", status, latest, fetched_at, age, None, items)
    except NewsProviderError as exc:
        return NewsHealthResult(
            "ERROR", FreshnessStatus.ERROR, None, fetched_at, None, str(exc)
        )

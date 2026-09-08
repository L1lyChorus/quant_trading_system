"""Freshness/health tests without network access."""

from datetime import datetime, timedelta, timezone

from data.health import FreshnessStatus, assess_market_freshness
from news.health import check_news_provider_health
from news.models import NewsCategory, NewsItemDTO, NewsRegion
from news.providers import NewsNetworkError, NewsProvider


def test_market_fresh_stale_outdated_unknown():
    now = datetime.now(timezone.utc)
    assert assess_market_freshness(now, now, 10, 20)[0] == FreshnessStatus.FRESH
    assert assess_market_freshness(now - timedelta(seconds=11), now, 10, 20)[0] == FreshnessStatus.STALE
    assert assess_market_freshness(now - timedelta(seconds=21), now, 10, 20)[0] == FreshnessStatus.OUTDATED
    assert assess_market_freshness(None, now, 10, 20)[0] == FreshnessStatus.UNKNOWN


class HealthProvider(NewsProvider):
    name = "health"

    def __init__(self, items=None, error=None):
        super().__init__("https://example.test")
        self.items = items
        self.error = error

    def fetch(self):
        if self.error:
            raise self.error
        return self.items


def test_news_unknown_and_error():
    now = datetime.now(timezone.utc)
    item = NewsItemDTO(
        "old", "", "health", "RSS", "https://example.test/1", None, now,
        NewsRegion.GLOBAL, NewsCategory.OTHER, "en"
    )
    unknown = check_news_provider_health(HealthProvider([item]))
    assert unknown.freshness == FreshnessStatus.UNKNOWN
    failed = check_news_provider_health(HealthProvider(error=NewsNetworkError("down")))
    assert failed.freshness == FreshnessStatus.ERROR


def test_news_old_content_is_not_fresh():
    now = datetime.now(timezone.utc)
    item = NewsItemDTO(
        "old", "", "health", "RSS", "https://example.test/2",
        now - timedelta(days=3), now, NewsRegion.GLOBAL, NewsCategory.OTHER, "en"
    )
    result = check_news_provider_health(HealthProvider([item]))
    assert result.freshness == FreshnessStatus.OUTDATED

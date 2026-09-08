"""Independent public-news ingestion and persistence."""

from news.models import NewsCategory, NewsItemDTO, NewsRegion
from news.health import FreshnessStatus, NewsHealthResult, check_news_provider_health
from news.providers import (
    ChinaDailyRSSProvider,
    ECBRSSProvider,
    FederalReserveRSSProvider,
    GovChinaRSSProvider,
    NewsProvider,
    NBSProvider,
    PBOCProvider,
)
from news.service import NewsRefreshResult, NewsService

__all__ = [
    "FederalReserveRSSProvider",
    "ChinaDailyRSSProvider",
    "ECBRSSProvider",
    "GovChinaRSSProvider",
    "NewsCategory",
    "NewsItemDTO",
    "NewsProvider",
    "NBSProvider",
    "PBOCProvider",
    "NewsRefreshResult",
    "NewsRegion",
    "NewsService",
    "FreshnessStatus",
    "NewsHealthResult",
    "check_news_provider_health",
]

"""News normalization, deduplication, and transactional persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database.models import NewsItem
from news.models import NewsItemDTO
from news.providers import (
    NewsFormatError,
    NewsNetworkError,
    NewsProvider,
    NewsProviderError,
    NewsUnavailableError,
)

logger = logging.getLogger(__name__)


@dataclass
class NewsRefreshResult:
    added: List[NewsItemDTO] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    provider_status: dict = field(default_factory=dict)
    provider_counts: dict = field(default_factory=dict)


class NewsService:
    """Refresh providers without touching accounts, orders, or positions."""

    def __init__(self, session: Session, enabled_providers=None) -> None:
        self.session = session
        self.enabled_providers = list(enabled_providers or [])

    def refresh_enabled(self) -> NewsRefreshResult:
        return self.refresh_news(providers=self.enabled_providers)

    def refresh_news(
        self, provider: Optional[NewsProvider] = None,
        providers: Optional[Iterable[NewsProvider]] = None,
    ) -> NewsRefreshResult:
        selected = list(providers or ([provider] if provider is not None else []))
        result = NewsRefreshResult()
        pending_urls = set()
        pending_source_titles = set()
        for current_provider in selected:
            provider_name = current_provider.name
            try:
                items = current_provider.fetch()
                result.provider_status[provider_name] = "AVAILABLE"
                result.provider_counts[provider_name] = len(items)
            except NewsUnavailableError as exc:
                result.provider_status[provider_name] = "UNAVAILABLE"
                result.provider_counts[provider_name] = 0
                result.errors.append("unavailable: " + str(exc))
                continue
            except NewsNetworkError as exc:
                result.provider_status[provider_name] = "ERROR"
                result.provider_counts[provider_name] = 0
                result.errors.append("network: " + str(exc))
                continue
            except NewsFormatError as exc:
                result.provider_status[provider_name] = "ERROR"
                result.provider_counts[provider_name] = 0
                result.errors.append("format: " + str(exc))
                continue
            except NewsProviderError as exc:
                result.provider_status[provider_name] = "ERROR"
                result.provider_counts[provider_name] = 0
                result.errors.append("provider: " + str(exc))
                continue
            except Exception as exc:
                result.provider_status[provider_name] = "ERROR"
                result.provider_counts[provider_name] = 0
                result.errors.append("provider: " + str(exc))
                continue

            for item in items:
                source_title = (item.source, item.title)
                if (
                    self._exists(item)
                    or item.url in pending_urls
                    or source_title in pending_source_titles
                ):
                    continue
                self.session.add(
                    NewsItem(
                        id=item.id,
                        title=item.title,
                        summary=item.summary,
                        source=item.source,
                        source_type=item.source_type,
                        url=item.url,
                        published_at=item.published_at,
                        fetched_at=item.fetched_at,
                        region=item.region.value,
                        category=item.category.value,
                        language=item.language,
                    )
                )
                result.added.append(item)
                pending_urls.add(item.url)
                pending_source_titles.add(source_title)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            result.errors.append("database constraint: " + str(exc.orig))
        except SQLAlchemyError as exc:
            self.session.rollback()
            result.errors.append("database: " + str(exc))
        return result

    def _exists(self, item: NewsItemDTO) -> bool:
        return self.session.scalar(
            select(NewsItem.id).where(
                (NewsItem.url == item.url)
                | (
                    (NewsItem.source == item.source)
                    & (NewsItem.title == item.title)
                )
            )
        ) is not None

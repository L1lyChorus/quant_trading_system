"""Offline news provider and persistence tests."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from database.connection import initialize_database
from database.models import Account, Execution, NewsItem, Order, Position
from news.models import NewsCategory, NewsItemDTO, NewsRegion, utc_now
from news.providers import (
    NewsFormatError,
    NewsNetworkError,
    NewsProvider,
    NewsUnavailableError,
    NBSProvider,
    PBOCProvider,
)
from news.service import NewsService


def item(url="https://example.test/a", title="Headline"):
    return NewsItemDTO(
        title=title,
        summary="summary",
        source="Test Source",
        source_type="RSS",
        url=url,
        published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        fetched_at=utc_now(),
        region=NewsRegion.GLOBAL,
        category=NewsCategory.MACRO,
        language="en",
    )


class StubProvider(NewsProvider):
    name = "Test Source"

    def __init__(self, items=None, error=None):
        super().__init__("https://example.test/rss")
        self.items = items or []
        self.error = error

    def fetch(self):
        if self.error:
            raise self.error
        return self.items


class OtherProvider(StubProvider):
    name = "Other Source"


@pytest.fixture
def database(tmp_path):
    return initialize_database("sqlite:///" + str(tmp_path / "news.db"))


def test_normalization_and_published_fetched_are_separate(database):
    source = item()
    with database.session() as session:
        result = NewsService(session).refresh_news(provider=StubProvider([source]))
        saved = session.get(NewsItem, source.id)
        assert len(result.added) == 1
        assert saved.published_at != saved.fetched_at
        assert saved.published_at.tzinfo is not None


def test_url_deduplication(database):
    source = item()
    with database.session() as session:
        service = NewsService(session)
        assert len(service.refresh_news(provider=StubProvider([source])).added) == 1
        assert len(service.refresh_news(provider=StubProvider([item(title="Other")])).added) == 0


def test_source_title_deduplication(database):
    source = item()
    with database.session() as session:
        service = NewsService(session)
        service.refresh_news(provider=StubProvider([source]))
        duplicate = item(url="https://example.test/b")
        assert service.refresh_news(provider=StubProvider([duplicate])).added == []


def test_empty_provider_result(database):
    with database.session() as session:
        result = NewsService(session).refresh_news(provider=StubProvider([]))
        assert result.added == [] and result.errors == []
        assert result.provider_status["Test Source"] == "AVAILABLE"
        assert result.provider_counts["Test Source"] == 0


def test_network_and_format_errors_are_separate(database):
    with database.session() as session:
        service = NewsService(session)
        network = service.refresh_news(provider=StubProvider(error=NewsNetworkError("down")))
        fmt = service.refresh_news(provider=StubProvider(error=NewsFormatError("bad xml")))
        assert network.errors[0].startswith("network:")
        assert fmt.errors[0].startswith("format:")
        assert network.provider_status["Test Source"] == "ERROR"


def test_provider_failure_does_not_delete_existing_news(database):
    source = item()
    with database.session() as session:
        service = NewsService(session)
        service.refresh_news(provider=StubProvider([source]))
        result = service.refresh_news(provider=StubProvider(error=NewsNetworkError("down")))
        assert result.errors
        assert session.scalar(select(NewsItem.id).where(NewsItem.url == source.url)) == source.id


def test_unavailable_provider_has_explicit_status(database):
    with database.session() as session:
        result = NewsService(session).refresh_news(
            provider=StubProvider(error=NewsUnavailableError("HTTP 404"))
        )
        assert result.provider_status["Test Source"] == "UNAVAILABLE"
        assert result.errors[0].startswith("unavailable:")


def test_one_provider_failure_does_not_block_another(database):
    with database.session() as session:
        result = NewsService(session).refresh_news(
            providers=[
                StubProvider(error=NewsNetworkError("down")),
                OtherProvider([item(url="https://example.test/ok")]),
            ]
        )
        assert result.provider_status["Test Source"] == "ERROR"
        assert result.provider_status["Other Source"] == "AVAILABLE"
        assert len(result.added) == 1


def test_news_refresh_does_not_change_trading_records(database):
    with database.session() as session:
        account = Account(name="paper", initial_cash=1000, current_cash=1000)
        session.add(account)
        session.commit()
        NewsService(session).refresh_news(provider=StubProvider([item()]))
        assert session.query(Account).count() == 1
        assert session.query(Order).count() == 0
        assert session.query(Execution).count() == 0
        assert session.query(Position).count() == 0


def test_news_provider_does_not_generate_signals():
    provider = StubProvider([item()])
    assert not hasattr(provider, "generate_signal")


def test_pboc_and_nbs_rss_adapters_parse_requested_feed_shapes(monkeypatch):
    payload = (
        "<rss><channel><item><title>标题</title>"
        "<link>https://example.test/item</link>"
        "<pubTime>2026-09-04 09:30:00</pubTime>"
        "<description>摘要</description></item></channel></rss>"
    ).encode("utf-8")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return payload

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    pboc_item = PBOCProvider().fetch()[0]
    nbs_item = NBSProvider("interpretation").fetch()[0]
    assert pboc_item.source == "PBOC"
    assert nbs_item.source == "NBS interpretation"
    assert pboc_item.published_at != pboc_item.fetched_at
    assert nbs_item.published_at is not None

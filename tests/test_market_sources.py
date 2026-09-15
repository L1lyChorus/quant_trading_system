"""Offline tests for source adapters, fallback, and market calendar."""

from datetime import datetime

from data.health import FreshnessStatus
from data.a_share import MarketDataError
from data.market import (
    EastmoneyMarketDataProvider,
    PrimaryFallbackMarketProvider,
    TencentMarketDataProvider,
)
from market_calendar import MarketSession, session_status


def test_eastmoney_unknown_timestamp(monkeypatch):
    payload = (
        '{"data":{"f57":"600000","f58":"浦发银行","f43":923,"f46":900,'
        '"f44":950,"f45":890,"f60":920,"f47":100,"f48":1000}}'
    ).encode("utf-8")
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return payload
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    quote = EastmoneyMarketDataProvider().fetch_quote()
    assert quote.freshness_status == FreshnessStatus.UNKNOWN
    assert quote.data_timestamp is None


def test_market_calendar_weekend_and_sessions():
    assert session_status(datetime(2026, 9, 12, 10, 0, tzinfo=__import__("datetime").timezone.utc)) == MarketSession.MARKET_CLOSED
    assert session_status(datetime(2026, 9, 8, 2, 0, tzinfo=__import__("datetime").timezone.utc)) == MarketSession.TRADING
    assert session_status(datetime(2026, 9, 8, 4, 0, tzinfo=__import__("datetime").timezone.utc)) == MarketSession.MIDDAY_BREAK


def test_primary_fallback_only_uses_fallback_after_primary_error():
    class Broken(TencentMarketDataProvider):
        def fetch_quote(self, symbol):
            raise MarketDataError("primary down")

    class Working(TencentMarketDataProvider):
        def fetch_quote(self, symbol):
            return "fallback-quote"

    quote, source = PrimaryFallbackMarketProvider(Broken(), Working()).fetch_quote("600000")
    assert quote == "fallback-quote"
    assert source.startswith("FALLBACK_AFTER_ERROR")

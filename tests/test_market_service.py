"""Offline tests for the application-facing market-data facade."""

from datetime import date

import pandas as pd

from data.market import MarketQuote
from data.service import MarketDataService
from database.connection import initialize_database
from data.historical import HistoricalDataProvider, HistoricalDataService
from sqlalchemy import select
from database.models import MarketBar


class Provider(HistoricalDataProvider):
    source = "MOCK"

    def __init__(self):
        self.requested = []

    def fetch(self, symbol, start=None, end=None):
        self.requested.append((symbol, start, end))
        frame = pd.DataFrame(
            [
                ["600000", "2024-01-03T00:00:00Z", 3, 4, 2, 3, 30],
                ["600000", "2024-01-01T00:00:00Z", 1, 2, 1, 1, 10],
                ["600000", date.today().isoformat() + "T00:00:00Z", 2, 3, 1, 2, 20],
            ],
            columns=["symbol", "datetime", "open", "high", "low", "close", "volume"],
        )
        frame["symbol"] = symbol
        return frame


class QuoteProvider:
    def __init__(self):
        self.requested = []

    def fetch_quote(self, symbol):
        self.requested.append(symbol)
        return MarketQuote(
            symbol=symbol, name=None, price=1, open=1, high=1, low=1,
            previous_close=1, volume=1, amount=1, data_timestamp=None,
            fetched_at=pd.Timestamp.now(tz="UTC").to_pydatetime(), source="MOCK",
            market_status="UNKNOWN", freshness_status="UNKNOWN", data_age=None,
        )


class EmptyProvider(HistoricalDataProvider):
    source = "EMPTY"

    def fetch(self, symbol, start=None, end=None):
        return pd.DataFrame(
            columns=["symbol", "datetime", "open", "high", "low", "close", "volume"]
        )


def test_service_canonicalizes_quote_and_historical_queries(tmp_path):
    provider = Provider()
    quote_provider = QuoteProvider()
    database = initialize_database("sqlite:///" + str(tmp_path / "market.db"))
    service = MarketDataService(
        quote_provider, HistoricalDataService(database, provider)
    )

    assert service.get_latest_quote("600000").symbol == "600000.SH"
    bars = service.get_historical_bars(
        "600000.SH", start_date="2024-01-01", end_date="2024-01-03",
        finalized_only=True,
    )

    assert quote_provider.requested == ["600000.SH"]
    assert provider.requested[0][0] == "600000.SH"
    assert [bar.datetime.date().isoformat() for bar in bars] == [
        "2024-01-01", "2024-01-03"
    ]
    assert all(bar.symbol == "600000.SH" for bar in bars)
    assert all(bar.bar_status == "FINAL" for bar in bars)


def test_service_can_include_intraday_and_returns_sorted_empty_ranges(tmp_path):
    database = initialize_database("sqlite:///" + str(tmp_path / "market.db"))
    service = MarketDataService(
        QuoteProvider(), HistoricalDataService(database, Provider())
    )

    bars = service.get_historical_bars("600000", finalized_only=False)
    assert [bar.datetime for bar in bars] == sorted(bar.datetime for bar in bars)
    assert any(bar.bar_status == "INTRADAY" for bar in bars)
    assert service.get_historical_bars(
        "600000", start_date="2030-01-01", end_date="2030-01-02"
    ) == []


def test_service_empty_provider_returns_no_data_and_canonical_inputs_do_not_duplicate(
    tmp_path,
):
    database = initialize_database("sqlite:///" + str(tmp_path / "market.db"))
    provider = Provider()
    service = MarketDataService(
        QuoteProvider(), HistoricalDataService(database, provider)
    )

    service.get_historical_bars("600000")
    service.get_historical_bars("600000.SH")
    with database.session() as session:
        assert session.scalars(
            select(MarketBar).where(MarketBar.symbol == "600000.SH")
        ).all()
        assert len(session.scalars(select(MarketBar)).all()) == 3

    empty_database = initialize_database("sqlite:///" + str(tmp_path / "empty.db"))
    empty_service = MarketDataService(
        QuoteProvider(), HistoricalDataService(empty_database, EmptyProvider())
    )
    assert empty_service.get_historical_bars("000001") == []

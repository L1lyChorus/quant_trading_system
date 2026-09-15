"""Offline tests for historical OHLCV normalization and persistence."""

from datetime import date, datetime, timezone
import json

import pandas as pd
import pytest

from data.historical import (
    EastmoneyHistoricalDataProvider,
    HistoricalDataError,
    HistoricalDataProvider,
    HistoricalDataService,
    HistoricalFetchStatus,
    PrimaryFallbackHistoricalDataProvider,
    SinaHistoricalDataProvider,
)
from database.connection import initialize_database


class MockProvider(HistoricalDataProvider):
    source = "MOCK"

    def __init__(self, frame):
        self.frame = frame

    def fetch(self, symbol, start=None, end=None):
        return self.frame[self.frame["symbol"] == symbol].copy()


def rows():
    return pd.DataFrame(
        [
            ["600000", "2024-01-03T01:00:00Z", 10, 11, 9, 10.5, 100],
            ["600000", "2024-01-02T01:00:00Z", 9, 10, 8, 9.5, 90],
            ["600000", "2024-01-02T01:00:00Z", 9, 10, 8, 9.5, 90],
        ],
        columns=["symbol", "datetime", "open", "high", "low", "close", "volume"],
    )


def test_mock_provider_deduplicates_sorts_and_records_source(tmp_path):
    database = initialize_database("sqlite:///" + str(tmp_path / "bars.db"))
    service = HistoricalDataService(database, MockProvider(rows()))

    assert service.update("600000") == 2
    bars = service.bars("600000")
    assert [bar.datetime for bar in bars] == sorted(bar.datetime for bar in bars)
    assert bars[0].source == "MOCK"
    assert bars[0].fetched_at.tzinfo == timezone.utc


def test_incremental_update_and_database_restart_are_idempotent(tmp_path):
    path = tmp_path / "bars.db"
    first = initialize_database("sqlite:///" + str(path))
    frame = rows().iloc[:2].copy()
    service = HistoricalDataService(first, MockProvider(frame))
    assert service.update("600000") == 2
    assert service.update("600000") == 2

    restarted = initialize_database("sqlite:///" + str(path))
    assert len(HistoricalDataService(restarted, MockProvider(frame)).bars()) == 2


def test_quality_errors_are_not_persisted(tmp_path):
    frame = rows().iloc[:1].copy()
    frame.loc[0, "high"] = 1
    database = initialize_database("sqlite:///" + str(tmp_path / "bars.db"))
    with pytest.raises(HistoricalDataError, match="high"):
        HistoricalDataService(database, MockProvider(frame)).update("600000")
    assert HistoricalDataService(database, MockProvider(rows().iloc[:1])).bars() == []


def test_empty_primary_falls_back_to_secondary():
    class Empty(HistoricalDataProvider):
        source = "EASTMONEY"

        def fetch(self, symbol, start=None, end=None):
            return pd.DataFrame(columns=rows().columns)

    class Working(MockProvider):
        source = "SINA"

    provider = PrimaryFallbackHistoricalDataProvider(Empty(), Working(rows().iloc[:1]))
    result = provider.fetch_result("600000")
    assert result.status == HistoricalFetchStatus.SUCCESS
    assert result.source == "SINA"
    assert result.primary_error == "EMPTY"


def test_http_providers_support_mock_transport_and_metadata():
    eastmoney_payload = {
        "data": {"klines": ["2024-01-02,9,9.5,10,8,100"]}
    }
    eastmoney = EastmoneyHistoricalDataProvider(
        transport=lambda url: json.dumps(eastmoney_payload)
    ).fetch_result("600000.SH")
    sina_payload = [{"day": "2024-01-02", "open": "9", "high": "10",
                     "low": "8", "close": "9.5", "volume": "100"}]
    sina = SinaHistoricalDataProvider(
        transport=lambda url: "callback(%s);" % json.dumps(sina_payload)
    ).fetch_result("000001.SZ")
    assert eastmoney.status is HistoricalFetchStatus.SUCCESS
    assert eastmoney.upstream == "push2his.eastmoney.com"
    assert eastmoney.frame.iloc[0]["symbol"] == "600000"
    assert sina.status is HistoricalFetchStatus.SUCCESS
    assert sina.upstream == "quotes.sina.cn"


def test_canonical_symbols_and_each_bar_finality_are_persisted(tmp_path):
    today = date.today().isoformat()
    frame = pd.DataFrame(
        [["600000", "2020-01-02T01:00:00Z", 9, 10, 8, 9.5, 100],
         ["600000", today + "T01:00:00Z", 9, 10, 8, 9.5, 100]],
        columns=rows().columns,
    )
    database = initialize_database("sqlite:///" + str(tmp_path / "bars.db"))
    service = HistoricalDataService(database, MockProvider(frame))
    assert service.update("600000") == 2
    bars = service.bars("600000")
    assert {bar.symbol for bar in bars} == {"600000.SH"}
    assert [bar.bar_status for bar in bars] == ["FINAL", "INTRADAY"]

"""Offline tests for historical OHLCV normalization and persistence."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from data.historical import HistoricalDataError, HistoricalDataProvider, HistoricalDataService
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

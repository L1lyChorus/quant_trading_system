"""Tests for local CSV market data ingestion and validation."""

import pandas as pd
import pytest

from data import (
    DuplicatePolicy,
    DataValidationError,
    REQUIRED_COLUMNS,
    read_market_csv,
)


def _write_csv(tmp_path, rows, columns=None):
    frame = pd.DataFrame(rows, columns=columns or REQUIRED_COLUMNS)
    path = tmp_path / "market.csv"
    frame.to_csv(path, index=False)
    return path


def _valid_rows():
    return [
        ["aapl", "2020-01-02T09:31:00Z", 304, 306, 303, 305, 120],
        ["AAPL", "2020-01-02T09:30:00Z", 300, 305, 299, 304, 100],
    ]


def test_valid_csv_is_normalized_and_sorted(tmp_path):
    result = read_market_csv(_write_csv(tmp_path, _valid_rows()))
    assert list(result.columns) == [
        "symbol", "datetime", "open", "high", "low", "close", "volume"
    ]
    assert result["symbol"].tolist() == ["AAPL", "AAPL"]
    assert result["datetime"].is_monotonic_increasing


def test_missing_required_column_is_rejected(tmp_path):
    rows = [row[:-1] for row in _valid_rows()]
    with pytest.raises(DataValidationError, match="missing required columns"):
        read_market_csv(
            _write_csv(
                tmp_path,
                rows,
                ["symbol", "datetime", "open", "high", "low", "close"],
            )
        )


def test_empty_csv_is_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("symbol,datetime,open,high,low,close,volume\n")
    with pytest.raises(DataValidationError, match="empty"):
        read_market_csv(path)


def test_invalid_datetime_is_rejected(tmp_path):
    rows = _valid_rows()
    rows[0][1] = "not-a-date"
    with pytest.raises(DataValidationError, match="datetime"):
        read_market_csv(_write_csv(tmp_path, rows))


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("open", 0, "greater than 0"),
        ("high", 298, "high must"),
        ("volume", -1, "volume must"),
    ],
)
def test_abnormal_values_are_rejected(tmp_path, field, value, message):
    rows = _valid_rows()
    rows[0][["symbol", "datetime", "open", "high", "low", "close", "volume"].index(field)] = value
    with pytest.raises(DataValidationError, match=message):
        read_market_csv(_write_csv(tmp_path, rows))


def test_duplicates_raise_by_default_and_can_be_dropped(tmp_path):
    rows = _valid_rows() + [_valid_rows()[0]]
    path = _write_csv(tmp_path, rows)
    with pytest.raises(DataValidationError, match="duplicate"):
        read_market_csv(path)
    result = read_market_csv(path, duplicate_policy=DuplicatePolicy.DROP)
    assert len(result) == 2


def test_cutoff_is_simulation_timestamp_not_current_date(tmp_path):
    result = read_market_csv(
        _write_csv(tmp_path, _valid_rows()),
        cutoff="2020-01-02T09:30:00Z",
    )
    assert len(result) == 1
    assert result.iloc[0]["datetime"] == pd.Timestamp("2020-01-02T09:30:00Z")


def test_invalid_cutoff_is_rejected(tmp_path):
    with pytest.raises(DataValidationError, match="cutoff"):
        read_market_csv(_write_csv(tmp_path, _valid_rows()), cutoff="invalid")


def test_invalid_symbol_is_rejected(tmp_path):
    rows = _valid_rows()
    rows[0][0] = "AAPL NY"
    with pytest.raises(DataValidationError, match="symbol"):
        read_market_csv(_write_csv(tmp_path, rows))

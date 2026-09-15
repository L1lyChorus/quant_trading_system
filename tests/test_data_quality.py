import pandas as pd
import pytest

from data.quality import DataQualityEngine


def make_bars():
    return pd.DataFrame(
        [
            ["600000.SH", "2026-01-05", 10.0, 10.5, 9.8, 10.2, 1000],
            ["600000.SH", "2026-01-06", 10.2, 10.8, 10.0, 10.6, 1200],
            ["600000.SH", "2026-01-07", 10.6, 11.0, 10.4, 10.9, 1500],
        ],
        columns=[
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )


def test_clean_data_passes():
    report = DataQualityEngine().validate(make_bars())

    assert report.symbol == "600000.SH"
    assert report.total_bars == 3
    assert report.missing_bars == 0
    assert report.duplicate_bars == 0
    assert report.invalid_ohlc == 0
    assert report.abnormal_volume == 0
    assert report.timestamp_errors == 0
    assert report.price_anomalies == 0
    assert report.quality_score == 100.0
    assert report.passed is True


def test_invalid_ohlc_is_detected():
    bars = make_bars()
    bars.loc[1, "high"] = 9.0

    report = DataQualityEngine().validate(bars)

    assert report.invalid_ohlc == 1
    assert report.passed is False


def test_negative_volume_is_detected():
    bars = make_bars()
    bars.loc[1, "volume"] = -100

    report = DataQualityEngine().validate(bars)

    assert report.abnormal_volume == 1
    assert report.passed is False


def test_duplicate_timestamp_is_detected():
    bars = make_bars()
    bars.loc[2, "datetime"] = "2026-01-06"

    report = DataQualityEngine().validate(bars)

    assert report.duplicate_bars == 2
    assert report.passed is False


def test_timestamp_order_error_is_detected():
    bars = make_bars()
    bars.loc[2, "datetime"] = "2026-01-04"

    report = DataQualityEngine().validate(bars)

    assert report.timestamp_errors == 1
    assert report.passed is False


def test_large_price_jump_is_flagged():
    bars = make_bars()
    bars.loc[2, "close"] = 15.0

    report = DataQualityEngine().validate(bars)

    assert report.price_anomalies == 1
    assert report.passed is False


def test_missing_required_column_raises():
    bars = make_bars().drop(columns=["volume"])

    with pytest.raises(ValueError):
        DataQualityEngine().validate(bars)

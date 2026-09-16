import pandas as pd
import pytest

from research.features.basic import add_basic_features


def test_basic_features_are_calculated():
    frame = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14, 15, 16],
            "high": [11, 12, 13, 14, 15, 16, 17],
            "low": [9, 10, 11, 12, 13, 14, 15],
            "close": [11, 12, 13, 14, 15, 16, 17],
            "volume": [100, 120, 150, 180, 220, 260, 300],
        }
    )

    result = add_basic_features(frame)

    assert "return_1d" in result.columns
    assert "range_pct" in result.columns
    assert "close_location" in result.columns
    assert "volume_change" in result.columns
    assert "volatility_5d" in result.columns
    assert "future_return_1d" in result.columns
    assert "future_return_5d" in result.columns


def test_return_and_future_return():
    frame = pd.DataFrame(
        {
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10, 11, 12],
            "volume": [100, 100, 100],
        }
    )

    result = add_basic_features(frame)

    assert result.loc[1, "return_1d"] == pytest.approx(0.1)
    assert result.loc[0, "future_return_1d"] == pytest.approx(0.1)


def test_close_location():
    frame = pd.DataFrame(
        {
            "open": [10],
            "high": [20],
            "low": [10],
            "close": [15],
            "volume": [100],
        }
    )

    result = add_basic_features(frame)

    assert result.loc[0, "close_location"] == pytest.approx(0.5)


def test_missing_columns_are_rejected():
    frame = pd.DataFrame(
        {
            "open": [10],
            "high": [11],
            "low": [9],
            "close": [10],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        add_basic_features(frame)

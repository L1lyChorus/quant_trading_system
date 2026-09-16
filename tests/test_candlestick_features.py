import pandas as pd
import pytest

from research.features.candlestick import add_candlestick_features


def test_candlestick_features_are_calculated():
    frame = pd.DataFrame(
        {
            "open": [10, 12],
            "high": [15, 14],
            "low": [5, 10],
            "close": [13, 11],
        }
    )

    result = add_candlestick_features(frame)

    assert result.loc[0, "body_pct"] == pytest.approx(0.3)
    assert result.loc[0, "upper_shadow_pct"] == pytest.approx(0.2)
    assert result.loc[0, "lower_shadow_pct"] == pytest.approx(0.5)
    assert result.loc[0, "is_bullish"]
    assert not result.loc[0, "is_bearish"]


def test_bearish_candlestick():
    frame = pd.DataFrame(
        {
            "open": [15],
            "high": [16],
            "low": [10],
            "close": [12],
        }
    )

    result = add_candlestick_features(frame)

    assert result.loc[0, "is_bearish"]
    assert not result.loc[0, "is_bullish"]
    assert result.loc[0, "body_pct"] == pytest.approx(0.5)


def test_missing_columns_are_rejected():
    frame = pd.DataFrame(
        {
            "open": [10],
            "high": [11],
            "close": [10],
        }
    )

    with pytest.raises(ValueError, match="missing required columns"):
        add_candlestick_features(frame)


def test_zero_range_does_not_crash():
    frame = pd.DataFrame(
        {
            "open": [10],
            "high": [10],
            "low": [10],
            "close": [10],
        }
    )

    result = add_candlestick_features(frame)

    assert pd.isna(result.loc[0, "body_pct"])
    assert pd.isna(result.loc[0, "upper_shadow_pct"])
    assert pd.isna(result.loc[0, "lower_shadow_pct"])

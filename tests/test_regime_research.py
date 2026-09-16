import pandas as pd
import pytest

from research.regime.research import RegimeResearchAnalyzer


def test_regime_research_analyzes_each_regime():
    frame = pd.DataFrame(
        {
            "regime_label": [
                "BULL_NORMAL_HIGH",
                "BULL_NORMAL_HIGH",
                "BEAR_HIGH_LOW",
                "BEAR_HIGH_LOW",
                "SIDEWAYS_LOW_NORMAL",
            ],
            "future_return_5d": [
                0.10,
                0.20,
                -0.10,
                -0.20,
                0.05,
            ],
        }
    )

    result = RegimeResearchAnalyzer().analyze(
        frame,
        lambda data: pd.Series(True, index=data.index),
    )

    assert set(result["regime_label"]) == {
        "BULL_NORMAL_HIGH",
        "BEAR_HIGH_LOW",
        "SIDEWAYS_LOW_NORMAL",
    }

    bull = result[
        result["regime_label"] == "BULL_NORMAL_HIGH"
    ].iloc[0]

    bear = result[
        result["regime_label"] == "BEAR_HIGH_LOW"
    ].iloc[0]

    assert bull["sample_size"] == 2
    assert bull["mean_return"] == pytest.approx(0.15)
    assert bull["win_rate"] == pytest.approx(1.0)

    assert bear["sample_size"] == 2
    assert bear["mean_return"] == pytest.approx(-0.15)
    assert bear["win_rate"] == pytest.approx(0.0)


def test_regime_research_requires_regime_label():
    frame = pd.DataFrame(
        {
            "future_return_5d": [0.10, 0.20],
        }
    )

    with pytest.raises(ValueError, match="regime_label"):
        RegimeResearchAnalyzer().analyze(
            frame,
            lambda data: pd.Series(True, index=data.index),
        )


def test_filter_regime_by_single_dimension():
    frame = pd.DataFrame(
        {
            "trend_state": ["BULL", "BULL", "BEAR"],
            "volatility_state": ["NORMAL", "HIGH", "HIGH"],
            "liquidity_state": ["HIGH", "LOW", "LOW"],
        }
    )

    result = RegimeResearchAnalyzer().filter_regime(
        frame,
        trend="BULL",
    )

    assert len(result) == 2
    assert set(result["trend_state"]) == {"BULL"}


def test_filter_regime_by_multiple_dimensions():
    frame = pd.DataFrame(
        {
            "trend_state": ["BULL", "BULL", "BEAR", "BULL"],
            "volatility_state": ["NORMAL", "HIGH", "HIGH", "HIGH"],
            "liquidity_state": ["HIGH", "LOW", "LOW", "HIGH"],
        }
    )

    result = RegimeResearchAnalyzer().filter_regime(
        frame,
        trend="BULL",
        volatility="HIGH",
        liquidity="LOW",
    )

    assert len(result) == 1
    assert result.iloc[0]["trend_state"] == "BULL"


def test_filter_regime_can_return_empty_result():
    frame = pd.DataFrame(
        {
            "trend_state": ["BULL", "BEAR"],
            "volatility_state": ["NORMAL", "HIGH"],
            "liquidity_state": ["HIGH", "LOW"],
        }
    )

    result = RegimeResearchAnalyzer().filter_regime(
        frame,
        trend="SIDEWAYS",
    )

    assert result.empty

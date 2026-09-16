import pandas as pd
import pytest

from research.regime.analyzer import RegimeAnalyzer


def test_regime_analyzer_counts_and_frequency():
    frame = pd.DataFrame(
        {
            "regime_label": [
                "BULL_NORMAL_HIGH",
                "BULL_NORMAL_HIGH",
                "BEAR_HIGH_LOW",
                "SIDEWAYS_LOW_NORMAL",
            ]
        }
    )

    result = RegimeAnalyzer().analyze(frame)

    bull = result[result["regime_label"] == "BULL_NORMAL_HIGH"].iloc[0]

    assert bull["sample_size"] == 2
    assert bull["frequency"] == pytest.approx(0.5)


def test_regime_analyzer_missing_column():
    frame = pd.DataFrame({"close": [100, 101]})

    with pytest.raises(ValueError, match="regime_label"):
        RegimeAnalyzer().analyze(frame)

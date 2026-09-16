import pandas as pd
import pytest

from research.pipeline import ResearchPipeline


def test_pipeline_builds_features_and_analyzes():
    frame = pd.DataFrame(
        {
            "open": [10, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "high": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            "low": [9, 9, 10, 11, 12, 13, 14, 15, 16, 17],
            "close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "volume": [100, 180, 200, 150, 250, 300, 320, 330, 340, 350],
        }
    )

    pipeline = ResearchPipeline()

    result = pipeline.analyze(
        frame,
        lambda data: data["volume_change"] > 0.4,
    )

    assert result.sample_size == 2
    assert result.mean_return == pytest.approx(((16 / 11 - 1) + (19 / 14 - 1)) / 2)


def test_prepare_features_contains_basic_and_candlestick_features():
    frame = pd.DataFrame(
        {
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [11, 12, 13],
            "volume": [100, 120, 150],
        }
    )

    result = ResearchPipeline().prepare_features(frame)

    assert "return_1d" in result.columns
    assert "volume_change" in result.columns
    assert "future_return_5d" in result.columns
    assert "body_pct" in result.columns
    assert "upper_shadow_pct" in result.columns
    assert "lower_shadow_pct" in result.columns
    assert "is_bullish" in result.columns

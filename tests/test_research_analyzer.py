import pandas as pd
import pytest

from research.analyzer import ResearchAnalyzer


def test_analyze_condition():
    frame = pd.DataFrame(
        {
            "volume_change": [0.1, 0.8, 1.2, 0.2, 0.9],
            "future_return_5d": [
                0.02,
                0.10,
                -0.05,
                0.03,
                0.07,
            ],
        }
    )

    result = ResearchAnalyzer().analyze(
        frame,
        lambda data: data["volume_change"] > 0.5,
    )

    assert result.sample_size == 3
    assert result.mean_return == pytest.approx(0.04)
    assert result.median_return == pytest.approx(0.07)
    assert result.win_rate == pytest.approx(2 / 3)
    assert result.max_gain == pytest.approx(0.10)
    assert result.max_drawdown == pytest.approx(-0.05)


def test_custom_future_return_column():
    frame = pd.DataFrame(
        {
            "signal": [True, False, True],
            "future_return_1d": [0.05, -0.02, 0.03],
        }
    )

    result = ResearchAnalyzer().analyze(
        frame,
        lambda data: data["signal"],
        future_return_column="future_return_1d",
    )

    assert result.sample_size == 2
    assert result.mean_return == pytest.approx(0.04)
    assert result.win_rate == 1.0


def test_missing_future_return_column_is_rejected():
    frame = pd.DataFrame({"signal": [True, False]})

    with pytest.raises(
        ValueError,
        match="missing future return column",
    ):
        ResearchAnalyzer().analyze(
            frame,
            lambda data: data["signal"],
        )


def test_empty_sample_is_rejected():
    frame = pd.DataFrame(
        {
            "volume_change": [0.1, 0.2],
            "future_return_5d": [0.01, -0.02],
        }
    )

    with pytest.raises(
        ValueError,
        match="no valid samples",
    ):
        ResearchAnalyzer().analyze(
            frame,
            lambda data: data["volume_change"] > 1.0,
        )


def test_invalid_condition_is_rejected():
    frame = pd.DataFrame(
        {
            "volume_change": [0.1],
            "future_return_5d": [0.02],
        }
    )

    with pytest.raises(
        ValueError,
        match="condition must return a pandas Series",
    ):
        ResearchAnalyzer().analyze(
            frame,
            lambda data: True,
        )


def test_max_drawdown_is_calculated_from_equity_curve():
    frame = pd.DataFrame(
        {
            "future_return_5d": [
                0.10,
                -0.05,
                0.03,
                -0.08,
            ]
        }
    )

    result = ResearchAnalyzer().analyze(
        frame,
        lambda data: pd.Series(True, index=data.index),
    )

    expected_equity = [
        1.10,
        1.045,
        1.07635,
        0.990242,
    ]

    expected_drawdown = (
        expected_equity[-1] / max(expected_equity) - 1
    )

    assert result.max_drawdown == pytest.approx(
        expected_drawdown
    )

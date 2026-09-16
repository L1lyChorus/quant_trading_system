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


def test_compare_condition_and_control():
    frame = pd.DataFrame(
        {
            "signal": [True, True, False, False, False],
            "future_return_5d": [
                0.10,
                0.06,
                0.01,
                -0.02,
                0.03,
            ],
        }
    )

    result = ResearchAnalyzer().compare(
        frame,
        lambda data: data["signal"],
    )

    assert result.condition.sample_size == 2
    assert result.condition.mean_return == pytest.approx(0.08)
    assert result.condition.win_rate == pytest.approx(1.0)

    assert result.control.sample_size == 3
    assert result.control.mean_return == pytest.approx(0.0066666667)
    assert result.control.win_rate == pytest.approx(2 / 3)

    assert result.mean_return_difference == pytest.approx(
        0.0733333333
    )
    assert result.win_rate_difference == pytest.approx(
        1 / 3
    )


def test_compare_uses_custom_future_return_column():
    frame = pd.DataFrame(
        {
            "signal": [True, False, True, False],
            "future_return_1d": [0.04, -0.01, 0.06, 0.02],
        }
    )

    result = ResearchAnalyzer().compare(
        frame,
        lambda data: data["signal"],
        future_return_column="future_return_1d",
    )

    assert result.condition.mean_return == pytest.approx(0.05)
    assert result.control.mean_return == pytest.approx(0.005)
    assert result.mean_return_difference == pytest.approx(0.045)


def test_compare_requires_future_return_column():
    frame = pd.DataFrame(
        {
            "signal": [True, False],
        }
    )

    with pytest.raises(
        ValueError,
        match="missing future return column",
    ):
        ResearchAnalyzer().compare(
            frame,
            lambda data: data["signal"],
        )


def test_compare_rejects_invalid_condition():
    frame = pd.DataFrame(
        {
            "signal": [True, False],
            "future_return_5d": [0.05, 0.01],
        }
    )

    with pytest.raises(
        ValueError,
        match="condition must return a pandas Series",
    ):
        ResearchAnalyzer().compare(
            frame,
            lambda data: True,
        )

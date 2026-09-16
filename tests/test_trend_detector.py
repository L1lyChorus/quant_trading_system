import pandas as pd
import pytest

from research.regime.detector import TrendDetector
from research.regime.models import TrendState


def test_trend_detector_bull():
    close = [100] * 60 + [100 + i * 2 for i in range(1, 21)]
    frame = pd.DataFrame({"close": close})

    result = TrendDetector().detect(frame)

    assert result.iloc[-1] == TrendState.BULL.value


def test_trend_detector_bear():
    close = [100] * 60 + [100 - i * 2 for i in range(1, 21)]
    frame = pd.DataFrame({"close": close})

    result = TrendDetector().detect(frame)

    assert result.iloc[-1] == TrendState.BEAR.value


def test_trend_detector_unknown_when_data_insufficient():
    frame = pd.DataFrame({"close": [100] * 30})

    result = TrendDetector().detect(frame)

    assert result.iloc[-1] == TrendState.UNKNOWN.value


def test_trend_detector_missing_close():
    frame = pd.DataFrame({"open": [100] * 10})

    with pytest.raises(ValueError, match="close"):
        TrendDetector().detect(frame)

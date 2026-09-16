import pandas as pd
import pytest

from research.regime.detector import LiquidityDetector
from research.regime.models import LiquidityState


def test_liquidity_detector_high():
    volume = [100] * 20 + [200]
    frame = pd.DataFrame({"volume": volume})

    result = LiquidityDetector().detect(frame)

    assert result.iloc[-1] == LiquidityState.HIGH.value


def test_liquidity_detector_low():
    volume = [100] * 20 + [50]
    frame = pd.DataFrame({"volume": volume})

    result = LiquidityDetector().detect(frame)

    assert result.iloc[-1] == LiquidityState.LOW.value


def test_liquidity_detector_normal():
    volume = [100] * 20 + [100]
    frame = pd.DataFrame({"volume": volume})

    result = LiquidityDetector().detect(frame)

    assert result.iloc[-1] == LiquidityState.NORMAL.value


def test_liquidity_detector_unknown_when_data_insufficient():
    frame = pd.DataFrame({"volume": [100] * 10})

    result = LiquidityDetector().detect(frame)

    assert result.iloc[-1] == LiquidityState.UNKNOWN.value


def test_liquidity_detector_missing_volume():
    frame = pd.DataFrame({"close": [100] * 20})

    with pytest.raises(ValueError, match="volume"):
        LiquidityDetector().detect(frame)

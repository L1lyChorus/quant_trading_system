import pandas as pd
import pytest

from research.regime.detector import MarketRegimeDetector
from research.regime.models import (
    LiquidityState,
    TrendState,
    VolatilityState,
)


def test_market_regime_detector():
    close = [100] * 60 + [100 + i * 2 for i in range(1, 21)]
    volume = [100] * 80

    frame = pd.DataFrame({
        "close": close,
        "volume": volume,
    })

    detector = MarketRegimeDetector()
    result = detector.detect(frame)

    assert "trend_state" in result.columns
    assert "volatility_state" in result.columns
    assert "liquidity_state" in result.columns
    assert "regime_label" in result.columns


def test_market_regime_detector_latest():
    close = [100] * 60 + [100 + i * 2 for i in range(1, 21)]
    volume = [100] * 80

    frame = pd.DataFrame({
        "close": close,
        "volume": volume,
    })

    regime = MarketRegimeDetector().detect_latest(frame)

    assert regime.trend == TrendState.BULL
    assert regime.volatility in {
        VolatilityState.LOW,
        VolatilityState.NORMAL,
        VolatilityState.HIGH,
    }
    assert regime.liquidity == LiquidityState.NORMAL


def test_market_regime_detector_empty_frame():
    frame = pd.DataFrame(columns=["close", "volume"])

    with pytest.raises(ValueError, match="empty"):
        MarketRegimeDetector().detect_latest(frame)

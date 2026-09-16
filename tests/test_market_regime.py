from research.regime.models import (
    LiquidityState,
    MarketRegime,
    TrendState,
    VolatilityState,
)


def test_market_regime_label():
    regime = MarketRegime(
        trend=TrendState.BULL,
        volatility=VolatilityState.NORMAL,
        liquidity=LiquidityState.HIGH,
    )

    assert regime.label == "BULL_NORMAL_HIGH"


def test_market_regime_unknown_states():
    regime = MarketRegime(
        trend=TrendState.UNKNOWN,
        volatility=VolatilityState.UNKNOWN,
        liquidity=LiquidityState.UNKNOWN,
    )

    assert regime.label == "UNKNOWN_UNKNOWN_UNKNOWN"

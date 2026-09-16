from __future__ import annotations

import pandas as pd

from research.regime.models import (
    LiquidityState,
    MarketRegime,
    TrendState,
    VolatilityState,
)


class TrendDetector:
    """基于短期/长期移动平均线判断市场趋势。"""

    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 60,
        sideways_threshold: float = 0.01,
    ) -> None:
        if short_window <= 0:
            raise ValueError("short_window must be greater than 0")

        if long_window <= short_window:
            raise ValueError("long_window must be greater than short_window")

        if sideways_threshold < 0:
            raise ValueError("sideways_threshold must not be negative")

        self.short_window = short_window
        self.long_window = long_window
        self.sideways_threshold = sideways_threshold

    def detect(self, frame: pd.DataFrame) -> pd.Series:
        if "close" not in frame.columns:
            raise ValueError("missing required column: close")

        close = pd.to_numeric(frame["close"], errors="coerce")

        short_ma = close.rolling(self.short_window).mean()
        long_ma = close.rolling(self.long_window).mean()

        result = pd.Series(
            TrendState.UNKNOWN.value,
            index=frame.index,
            dtype="object",
        )

        valid = short_ma.notna() & long_ma.notna()

        relative_difference = (
            (short_ma - long_ma).abs() / long_ma
        )

        sideways = valid & (
            relative_difference <= self.sideways_threshold
        )

        bull = valid & (short_ma > long_ma) & ~sideways
        bear = valid & (short_ma < long_ma) & ~sideways

        result.loc[sideways] = TrendState.SIDEWAYS.value
        result.loc[bull] = TrendState.BULL.value
        result.loc[bear] = TrendState.BEAR.value

        return result


class VolatilityDetector:
    """基于滚动收益率标准差判断市场波动状态。"""

    def __init__(
        self,
        window: int = 20,
        baseline_window: int = 60,
        low_threshold: float = 0.8,
        high_threshold: float = 1.2,
    ) -> None:
        if window <= 0:
            raise ValueError("window must be greater than 0")

        if baseline_window <= window:
            raise ValueError(
                "baseline_window must be greater than window"
            )

        if low_threshold <= 0:
            raise ValueError("low_threshold must be greater than 0")

        if high_threshold <= low_threshold:
            raise ValueError(
                "high_threshold must be greater than low_threshold"
            )

        self.window = window
        self.baseline_window = baseline_window
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

    def detect(self, frame: pd.DataFrame) -> pd.Series:
        if "close" not in frame.columns:
            raise ValueError("missing required column: close")

        close = pd.to_numeric(frame["close"], errors="coerce")

        returns = close.pct_change()
        current_volatility = returns.rolling(self.window).std()

        baseline_volatility = (
            current_volatility
            .rolling(self.baseline_window)
            .median()
        )

        ratio = current_volatility / baseline_volatility

        result = pd.Series(
            VolatilityState.UNKNOWN.value,
            index=frame.index,
            dtype="object",
        )

        valid = ratio.notna()

        low = valid & (ratio < self.low_threshold)
        high = valid & (ratio > self.high_threshold)
        normal = valid & ~low & ~high

        result.loc[low] = VolatilityState.LOW.value
        result.loc[normal] = VolatilityState.NORMAL.value
        result.loc[high] = VolatilityState.HIGH.value

        return result


class LiquidityDetector:
    """基于相对成交量判断市场流动性状态。"""

    def __init__(
        self,
        window: int = 20,
        low_threshold: float = 0.8,
        high_threshold: float = 1.2,
    ) -> None:
        if window <= 0:
            raise ValueError("window must be greater than 0")

        if low_threshold <= 0:
            raise ValueError("low_threshold must be greater than 0")

        if high_threshold <= low_threshold:
            raise ValueError(
                "high_threshold must be greater than low_threshold"
            )

        self.window = window
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

    def detect(self, frame: pd.DataFrame) -> pd.Series:
        if "volume" not in frame.columns:
            raise ValueError("missing required column: volume")

        volume = pd.to_numeric(frame["volume"], errors="coerce")

        average_volume = volume.rolling(self.window).mean()
        relative_volume = volume / average_volume

        result = pd.Series(
            LiquidityState.UNKNOWN.value,
            index=frame.index,
            dtype="object",
        )

        valid = relative_volume.notna()

        low = valid & (relative_volume < self.low_threshold)
        high = valid & (relative_volume > self.high_threshold)
        normal = valid & ~low & ~high

        result.loc[low] = LiquidityState.LOW.value
        result.loc[normal] = LiquidityState.NORMAL.value
        result.loc[high] = LiquidityState.HIGH.value

        return result


class MarketRegimeDetector:
    """统一计算市场的趋势、波动率和流动性状态。"""

    def __init__(
        self,
        trend_detector: TrendDetector | None = None,
        volatility_detector: VolatilityDetector | None = None,
        liquidity_detector: LiquidityDetector | None = None,
    ) -> None:
        self.trend_detector = trend_detector or TrendDetector()
        self.volatility_detector = (
            volatility_detector or VolatilityDetector()
        )
        self.liquidity_detector = (
            liquidity_detector or LiquidityDetector()
        )

    def detect(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()

        result["trend_state"] = self.trend_detector.detect(frame)
        result["volatility_state"] = (
            self.volatility_detector.detect(frame)
        )
        result["liquidity_state"] = (
            self.liquidity_detector.detect(frame)
        )

        result["regime_label"] = (
            result["trend_state"]
            + "_"
            + result["volatility_state"]
            + "_"
            + result["liquidity_state"]
        )

        return result

    def detect_latest(self, frame: pd.DataFrame) -> MarketRegime:
        detected = self.detect(frame)

        if detected.empty:
            raise ValueError("frame must not be empty")

        latest = detected.iloc[-1]

        return MarketRegime(
            trend=TrendState(latest["trend_state"]),
            volatility=VolatilityState(latest["volatility_state"]),
            liquidity=LiquidityState(latest["liquidity_state"]),
        )

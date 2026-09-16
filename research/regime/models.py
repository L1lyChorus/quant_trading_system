from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrendState(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


class VolatilityState(str, Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class LiquidityState(str, Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MarketRegime:
    """某一时点的市场环境状态。"""

    trend: TrendState
    volatility: VolatilityState
    liquidity: LiquidityState

    @property
    def label(self) -> str:
        return (
            f"{self.trend.value}_"
            f"{self.volatility.value}_"
            f"{self.liquidity.value}"
        )

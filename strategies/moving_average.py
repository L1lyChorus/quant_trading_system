"""Moving average crossover signal strategy."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from data.validation import REQUIRED_COLUMNS, validate_market_data
from data.symbols import normalize_symbol
from strategies.base import Strategy
from strategies.signals import Signal, SignalAction


class MovingAverageCrossoverStrategy(Strategy):
    """Generate a signal only when short and long averages truly cross."""

    strategy_name = "moving_average_crossover"

    def __init__(self, short_window: int, long_window: int) -> None:
        if short_window <= 0 or long_window <= 0:
            raise ValueError("short_window and long_window must be greater than 0")
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(
        self,
        market_data: pd.DataFrame,
        symbol: str,
        current_position: Optional[Any] = None,
        simulation_time: Optional[datetime] = None,
        cutoff: Optional[datetime] = None,
    ) -> Signal:
        del current_position
        requested_symbol = normalize_symbol(symbol)
        if not requested_symbol:
            raise ValueError("symbol is required")
        if not isinstance(market_data, pd.DataFrame):
            raise ValueError("market_data must be a pandas DataFrame")

        data = validate_market_data(market_data)
        data = data[data["symbol"] == requested_symbol].copy()
        effective_cutoff = cutoff if cutoff is not None else simulation_time
        if effective_cutoff is not None:
            parsed_cutoff = pd.to_datetime(
                effective_cutoff, errors="coerce", utc=True
            )
            if pd.isna(parsed_cutoff):
                raise ValueError("cutoff must be a valid ISO 8601 datetime")
            data = data[data["datetime"] <= parsed_cutoff]
        data = data.sort_values("datetime", kind="stable").reset_index(drop=True)
        if data.empty:
            raise ValueError("no market data found for symbol before cutoff")

        data["short_ma"] = data["close"].rolling(self.short_window).mean()
        data["long_ma"] = data["close"].rolling(self.long_window).mean()
        current = data.iloc[-1]
        previous = data.iloc[-2] if len(data) >= 2 else None
        metadata = {
            "short_ma": self._float_or_none(current["short_ma"]),
            "long_ma": self._float_or_none(current["long_ma"]),
            "previous_short_ma": self._float_or_none(
                previous["short_ma"] if previous is not None else None
            ),
            "previous_long_ma": self._float_or_none(
                previous["long_ma"] if previous is not None else None
            ),
            "short_window": self.short_window,
            "long_window": self.long_window,
        }

        action = SignalAction.HOLD
        if pd.isna(current["long_ma"]):
            reason = "insufficient data for long_window"
        elif previous is None or pd.isna(previous["long_ma"]):
            reason = "long_window is available but no previous comparison point"
        elif (
            previous["short_ma"] <= previous["long_ma"]
            and current["short_ma"] > current["long_ma"]
        ):
            action = SignalAction.BUY
            reason = "short moving average crossed above long moving average"
        elif (
            previous["short_ma"] >= previous["long_ma"]
            and current["short_ma"] < current["long_ma"]
        ):
            action = SignalAction.SELL
            reason = "short moving average crossed below long moving average"
        else:
            reason = "no moving average crossover"

        timestamp = current["datetime"].to_pydatetime()
        return Signal(
            signal_id=self._signal_id(requested_symbol, timestamp, action),
            symbol=requested_symbol,
            action=action,
            timestamp=timestamp,
            price=float(current["close"]),
            strategy_name=self.strategy_name,
            reason=reason,
            metadata=metadata,
        )

    @staticmethod
    def _float_or_none(value: Any) -> Optional[float]:
        return None if value is None or pd.isna(value) else float(value)

    def _signal_id(
        self, symbol: str, timestamp: datetime, action: SignalAction
    ) -> str:
        value = "{}:{}:{}:{}".format(
            self.strategy_name, symbol, timestamp.isoformat(), action.value
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

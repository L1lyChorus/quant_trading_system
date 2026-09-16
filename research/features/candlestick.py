from __future__ import annotations

import pandas as pd


def add_candlestick_features(frame: pd.DataFrame) -> pd.DataFrame:
    """将 OHLC 数据转换为可用于统计研究的 K 线结构特征。"""

    required = {"open", "high", "low", "close"}

    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"missing required columns: {sorted(missing)}"
        )

    result = frame.copy()

    candle_range = result["high"] - result["low"]
    body = (result["close"] - result["open"]).abs()

    result["body_pct"] = body / candle_range

    result["upper_shadow_pct"] = (
        result["high"]
        - result[["open", "close"]].max(axis=1)
    ) / candle_range

    result["lower_shadow_pct"] = (
        result[["open", "close"]].min(axis=1)
        - result["low"]
    ) / candle_range

    result["is_bullish"] = result["close"] > result["open"]
    result["is_bearish"] = result["close"] < result["open"]

    result["candle_range_pct"] = candle_range / result["close"]

    return result

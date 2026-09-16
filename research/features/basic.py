from __future__ import annotations

import pandas as pd


def add_basic_features(frame: pd.DataFrame) -> pd.DataFrame:
    """为标准 OHLCV 数据添加基础研究特征。"""

    required = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"missing required columns: {sorted(missing)}"
        )

    result = frame.copy()

    previous_close = result["close"].shift(1)

    result["return_1d"] = result["close"].pct_change()

    result["range_pct"] = (
        (result["high"] - result["low"])
        / result["close"]
    )

    result["close_location"] = (
        (result["close"] - result["low"])
        / (result["high"] - result["low"])
    )

    result["volume_change"] = result["volume"].pct_change()

    result["volatility_5d"] = (
        result["return_1d"]
        .rolling(5)
        .std()
    )

    result["future_return_1d"] = (
        result["close"].shift(-1) / result["close"] - 1
    )

    result["future_return_5d"] = (
        result["close"].shift(-5) / result["close"] - 1
    )

    return result

"""Validation and normalization for OHLCV market data."""

from __future__ import annotations

import re
from typing import List

import pandas as pd

REQUIRED_COLUMNS = (
    "symbol",
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")


class DataValidationError(ValueError):
    """Raised when market data is missing, malformed, or unsafe to use."""


def _normalize_symbols(symbols: pd.Series) -> pd.Series:
    normalized = symbols.astype("string").str.strip().str.upper()
    invalid = normalized.isna() | (normalized == "") | ~normalized.str.match(
        _SYMBOL_PATTERN, na=False
    )
    if invalid.any():
        raise DataValidationError("symbol contains empty or invalid values")
    return normalized


def validate_market_data(data: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a normalized, chronologically sorted OHLCV frame."""
    if not isinstance(data, pd.DataFrame):
        raise DataValidationError("market data must be a pandas DataFrame")
    if data.empty:
        raise DataValidationError("market data is empty")

    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise DataValidationError(
            "market data is missing required columns: " + ", ".join(missing)
        )

    normalized = data.loc[:, REQUIRED_COLUMNS].copy()
    normalized["symbol"] = _normalize_symbols(normalized["symbol"])
    normalized["datetime"] = pd.to_datetime(
        normalized["datetime"], errors="coerce", utc=True
    )
    if normalized["datetime"].isna().any():
        raise DataValidationError("datetime contains invalid ISO 8601 values")

    for column in ("open", "high", "low", "close", "volume"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if normalized[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise DataValidationError("price and volume columns must contain numbers")
    if not normalized[["open", "high", "low", "close"]].gt(0).all().all():
        raise DataValidationError("open, high, low, and close must be greater than 0")
    if (normalized["high"] < normalized["low"]).any():
        raise DataValidationError("high must be greater than or equal to low")
    if (normalized["volume"] < 0).any():
        raise DataValidationError("volume must be greater than or equal to 0")

    return normalized.sort_values(
        ["datetime", "symbol"], kind="stable"
    ).reset_index(drop=True)

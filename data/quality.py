"""Historical market data quality checks."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class DataQualityReport:
    """Machine-readable result of a market data quality check."""

    symbol: str
    total_bars: int
    missing_bars: int
    duplicate_bars: int
    invalid_ohlc: int
    abnormal_volume: int
    timestamp_errors: int
    price_anomalies: int
    quality_score: float
    passed: bool


class DataQualityEngine:
    """Validate historical OHLCV data before research or backtesting."""

    def __init__(self, price_jump_threshold: float = 0.20) -> None:
        if price_jump_threshold <= 0:
            raise ValueError("price_jump_threshold must be positive")
        self.price_jump_threshold = price_jump_threshold

    def validate(self, bars: pd.DataFrame) -> DataQualityReport:
        """Validate a normalized historical OHLCV DataFrame."""

        self._validate_columns(bars)

        frame = bars.copy()

        if frame.empty:
            return DataQualityReport(
                symbol="",
                total_bars=0,
                missing_bars=0,
                duplicate_bars=0,
                invalid_ohlc=0,
                abnormal_volume=0,
                timestamp_errors=0,
                price_anomalies=0,
                quality_score=0.0,
                passed=False,
            )

        frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")

        symbol = str(frame["symbol"].dropna().iloc[0]) if frame["symbol"].notna().any() else ""

        total_bars = len(frame)

        missing_bars = int(frame[list(REQUIRED_COLUMNS)].isna().any(axis=1).sum())

        duplicate_bars = int(
            frame.duplicated(subset=["symbol", "datetime"], keep=False).sum()
        )

        timestamp_errors = self._count_timestamp_errors(frame)

        invalid_ohlc = int(
            (
                (frame["high"] < frame["open"])
                | (frame["high"] < frame["close"])
                | (frame["high"] < frame["low"])
                | (frame["low"] > frame["open"])
                | (frame["low"] > frame["close"])
            ).fillna(False).sum()
        )

        abnormal_volume = int((frame["volume"] < 0).fillna(False).sum())

        price_anomalies = self._count_price_anomalies(frame)

        quality_score = self._calculate_score(
            total_bars=total_bars,
            missing_bars=missing_bars,
            duplicate_bars=duplicate_bars,
            invalid_ohlc=invalid_ohlc,
            abnormal_volume=abnormal_volume,
            timestamp_errors=timestamp_errors,
            price_anomalies=price_anomalies,
        )

        passed = (
            total_bars > 0
            and missing_bars == 0
            and duplicate_bars == 0
            and invalid_ohlc == 0
            and abnormal_volume == 0
            and timestamp_errors == 0
            and quality_score >= 90.0
        )

        return DataQualityReport(
            symbol=symbol,
            total_bars=total_bars,
            missing_bars=missing_bars,
            duplicate_bars=duplicate_bars,
            invalid_ohlc=invalid_ohlc,
            abnormal_volume=abnormal_volume,
            timestamp_errors=timestamp_errors,
            price_anomalies=price_anomalies,
            quality_score=quality_score,
            passed=passed,
        )

    @staticmethod
    def _validate_columns(bars: pd.DataFrame) -> None:
        missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
        if missing:
            raise ValueError(
                "Missing required market data columns: {}".format(", ".join(missing))
            )

    @staticmethod
    def _count_timestamp_errors(frame: pd.DataFrame) -> int:
        errors = int(frame["datetime"].isna().sum())

        valid = frame.dropna(subset=["datetime"])

        if len(valid) > 1:
            errors += int((valid["datetime"].diff().dropna() <= pd.Timedelta(0)).sum())

        return errors

    def _count_price_anomalies(self, frame: pd.DataFrame) -> int:
        valid = frame.dropna(subset=["datetime", "close"]).sort_values(
            ["symbol", "datetime"]
        )

        if len(valid) < 2:
            return 0

        previous_close = valid.groupby("symbol")["close"].shift(1)

        returns = (valid["close"] / previous_close) - 1.0

        return int(
            (returns.abs() > self.price_jump_threshold)
            .fillna(False)
            .sum()
        )

    @staticmethod
    def _calculate_score(
        total_bars: int,
        missing_bars: int,
        duplicate_bars: int,
        invalid_ohlc: int,
        abnormal_volume: int,
        timestamp_errors: int,
        price_anomalies: int,
    ) -> float:
        if total_bars == 0:
            return 0.0

        penalties = (
            missing_bars
            + duplicate_bars
            + invalid_ohlc
            + abnormal_volume
            + timestamp_errors
            + price_anomalies
        )

        score = 100.0 * max(0.0, 1.0 - penalties / total_bars)

        return round(score, 2)

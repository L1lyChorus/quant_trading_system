"""Historical OHLCV providers and durable SQLite ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from sqlalchemy import select

from data.csv_reader import DuplicatePolicy, read_market_csv
from data.validation import DataValidationError, validate_market_data
from database.models import MarketBar


class HistoricalDataError(ValueError):
    """Raised when historical data cannot be fetched or persisted safely."""


class HistoricalDataProvider(ABC):
    source = "unknown"

    @abstractmethod
    def fetch(
        self, symbol: str, start: Optional[object] = None, end: Optional[object] = None
    ) -> pd.DataFrame:
        """Return normalized-compatible OHLCV rows for one symbol."""


class UserCSVHistoricalDataProvider(HistoricalDataProvider):
    """Explicit local-file provider for user-exported historical data."""

    source = "USER_CSV"

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def fetch(self, symbol: str, start: Optional[object] = None, end: Optional[object] = None) -> pd.DataFrame:
        try:
            frame = read_market_csv(self.path, duplicate_policy=DuplicatePolicy.DROP)
        except DataValidationError as exc:
            raise HistoricalDataError(str(exc)) from exc
        result = frame[frame["symbol"] == symbol.strip().upper()].copy()
        if start is not None:
            result = result[result["datetime"] >= pd.to_datetime(start, utc=True)]
        if end is not None:
            result = result[result["datetime"] <= pd.to_datetime(end, utc=True)]
        if result.empty:
            raise HistoricalDataError("no USER_CSV rows for requested symbol/range")
        return result.reset_index(drop=True)


class HistoricalDataService:
    def __init__(self, database, provider: HistoricalDataProvider) -> None:
        self.database = database
        self.provider = provider

    def update(
        self, symbol: str, start: Optional[object] = None, end: Optional[object] = None
    ) -> int:
        fetched_at = datetime.now(timezone.utc)
        try:
            frame = validate_market_data(self.provider.fetch(symbol, start, end))
        except (DataValidationError, HistoricalDataError) as exc:
            raise HistoricalDataError(str(exc)) from exc
        frame = frame.drop_duplicates(["symbol", "datetime"], keep="last")
        with self.database.session() as session:
            for row in frame.to_dict("records"):
                existing = session.scalar(
                    select(MarketBar).where(
                        MarketBar.symbol == row["symbol"],
                        MarketBar.datetime == row["datetime"].to_pydatetime(),
                    )
                )
                values = {
                    "symbol": row["symbol"],
                    "datetime": row["datetime"].to_pydatetime(),
                    "open": row["open"], "high": row["high"], "low": row["low"],
                    "close": row["close"], "volume": row["volume"],
                    "source": self.provider.source, "fetched_at": fetched_at,
                }
                if existing is None:
                    session.add(MarketBar(**values))
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)
            session.commit()
        return len(frame)

    def bars(self, symbol: Optional[str] = None):
        with self.database.session() as session:
            query = select(MarketBar).order_by(MarketBar.datetime, MarketBar.symbol)
            if symbol:
                query = query.where(MarketBar.symbol == symbol.upper())
            return list(session.scalars(query))

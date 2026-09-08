"""Application-facing market-data facade."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional

from data.historical import HistoricalDataService
from data.market import MarketDataProvider, MarketQuote
from data.symbols import normalize_symbol


class MarketDataService:
    """Expose normalized quotes and bars without leaking provider details."""

    def __init__(
        self,
        quote_provider: MarketDataProvider,
        historical_service: HistoricalDataService,
    ) -> None:
        self.quote_provider = quote_provider
        self.historical_service = historical_service

    def get_latest_quote(self, symbol: str) -> MarketQuote:
        return self.quote_provider.fetch_quote(normalize_symbol(symbol))

    def get_historical_bars(
        self,
        symbol: str,
        start_date: Optional[object] = None,
        end_date: Optional[object] = None,
        finalized_only: bool = True,
    ):
        canonical = normalize_symbol(symbol)
        self.historical_service.update(canonical, start=start_date, end=end_date)
        bars = self.historical_service.bars(canonical)
        start = self._boundary(start_date)
        end = self._boundary(end_date)
        return [
            bar
            for bar in bars
            if (not finalized_only or bar.bar_status == "FINAL")
            and (start is None or bar.datetime >= start)
            and (end is None or bar.datetime <= end)
        ]

    @staticmethod
    def _boundary(value: Optional[object]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

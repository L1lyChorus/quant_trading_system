"""Unified public A-share market quote providers."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from data.a_share import MarketDataError
from data.health import FreshnessStatus, assess_market_freshness
from market_calendar import MarketSession, session_status


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    name: Optional[str]
    price: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    previous_close: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    data_timestamp: Optional[datetime]
    fetched_at: datetime
    source: str
    market_status: str
    freshness_status: FreshnessStatus
    data_age: Optional[float]


class MarketDataProvider:
    source = "public market data"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    @staticmethod
    def _status(timestamp, fetched):
        status, age = assess_market_freshness(timestamp, fetched)
        return status, age

    @staticmethod
    def _market_status(fetched: datetime, freshness: FreshnessStatus) -> str:
        session = session_status(fetched)
        if session is not MarketSession.TRADING and freshness is FreshnessStatus.FRESH:
            return "{}_DELAYED".format(session.value)
        return session.value


class TencentMarketDataProvider(MarketDataProvider):
    source = "Tencent quote"

    def fetch_quote(self, symbol: str) -> MarketQuote:
        symbol = symbol.strip().upper()
        if not re.match(r"^[036]\d{5}$", symbol):
            raise MarketDataError("A-share symbol must be six digits")
        market = "sz" if symbol.startswith(("0", "3")) else "sh"
        url = "https://qt.gtimg.cn/q={}{}".format(market, symbol)
        fetched = datetime.now(timezone.utc)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "quant-trading-system/1.0"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("gbk", errors="replace")
        except OSError as exc:
            raise MarketDataError("Tencent quote network error: {}".format(exc)) from exc
        match = re.search(r'="([^"]*)"', raw)
        if not match:
            raise MarketDataError("Tencent quote response format error")
        fields = match.group(1).split("~")
        if len(fields) < 35:
            raise MarketDataError("Tencent quote response missing fields")

        def number(index):
            try:
                return float(fields[index]) if fields[index] else None
            except (ValueError, IndexError):
                return None

        timestamp = None
        try:
            timestamp = datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).astimezone(timezone.utc)
        except (ValueError, IndexError):
            pass
        status, age = self._status(timestamp, fetched)
        market_status = self._market_status(fetched, status)
        if market_status.endswith("_DELAYED"):
            status = FreshnessStatus.DELAYED
        return MarketQuote(
            symbol, fields[1] or None, number(3), number(5), number(33), number(34),
            number(4), number(6), number(37), timestamp, fetched, self.source,
            market_status, status, age,
        )


class EastmoneyMarketDataProvider(MarketDataProvider):
    source = "Eastmoney quote"
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get?"
        "secid=1.600000&fields=f57,f58,f43,f46,f44,f45,f47,f48,f60,f86"
    )

    def fetch_quote(self, symbol: str = "600000") -> MarketQuote:
        fetched = datetime.now(timezone.utc)
        try:
            request = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise MarketDataError("Eastmoney quote error: {}".format(exc)) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data.get("f57"):
            raise MarketDataError("Eastmoney quote response format error")

        def scaled(key):
            value = data.get(key)
            return float(value) / 100 if isinstance(value, (int, float)) else None

        status, age = self._status(None, fetched)
        market_status = self._market_status(fetched, status)
        if market_status.endswith("_DELAYED"):
            status = FreshnessStatus.DELAYED
        return MarketQuote(
            str(data["f57"]), data.get("f58"), scaled("f43"), scaled("f46"),
            scaled("f44"), scaled("f45"), scaled("f60"), data.get("f47"),
            data.get("f48"), None, fetched, self.source, market_status, status, age,
        )


class PrimaryFallbackMarketProvider:
    """Use fallback only after primary failure; preserve the provider result."""

    def __init__(self, primary: MarketDataProvider, fallback: MarketDataProvider):
        self.primary = primary
        self.fallback = fallback

    def fetch_quote(self, symbol: str):
        try:
            return self.primary.fetch_quote(symbol), "PRIMARY"
        except MarketDataError as primary_error:
            try:
                quote = self.fallback.fetch_quote(symbol)
                return quote, "FALLBACK_AFTER_ERROR: {}".format(primary_error)
            except MarketDataError as fallback_error:
                raise MarketDataError(
                    "primary failed: {}; fallback failed: {}".format(
                        primary_error, fallback_error
                    )
                ) from fallback_error

"""Public Tencent A-share quote adapter with explicit freshness metadata."""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from data.health import FreshnessStatus, MarketHealthResult, assess_market_freshness


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class AShareQuote:
    symbol: str
    name: Optional[str]
    data_timestamp: Optional[datetime]
    price: float
    source: str
    fetched_at: datetime
    freshness_status: FreshnessStatus
    data_age: Optional[float]


class TencentAShareProvider:
    """Read-only public quote endpoint; no key, account, or order access."""

    source = "Tencent quote"
    url_template = "https://qt.gtimg.cn/q={market}{symbol}"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def fetch_quote(self, symbol: str) -> AShareQuote:
        normalized = symbol.strip().upper()
        if not re.match(r"^[036]\d{5}$", normalized):
            raise MarketDataError("A-share symbol must be six digits")
        market = "sz" if normalized.startswith(("0", "3")) else "sh"
        url = self.url_template.format(market=market, symbol=normalized)
        fetched = datetime.now(timezone.utc)
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "quant-trading-system/1.0"}
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("gbk", errors="replace")
        except OSError as exc:
            raise MarketDataError("Tencent quote network error: {}".format(exc)) from exc
        match = re.search(r'="([^"]*)"', raw)
        if not match:
            raise MarketDataError("Tencent quote response format error")
        fields = match.group(1).split("~")
        if len(fields) < 30:
            raise MarketDataError("Tencent quote response missing fields")
        try:
            name = fields[1] or None
            price = float(fields[3])
            stamp = datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).astimezone(timezone.utc)
        except (ValueError, IndexError) as exc:
            raise MarketDataError("Tencent quote contains invalid values") from exc
        status, age = assess_market_freshness(stamp, fetched)
        return AShareQuote(
            normalized, name, stamp, price, self.source, fetched, status, age
        )

    def health_check(self, symbol: str) -> MarketHealthResult:
        fetched = datetime.now(timezone.utc)
        try:
            quote = self.fetch_quote(symbol)
            return MarketHealthResult(
                "AVAILABLE",
                quote.freshness_status,
                quote.data_timestamp,
                fetched,
                quote.data_age,
                None,
                quote,
            )
        except MarketDataError as exc:
            return MarketHealthResult(
                "ERROR", FreshnessStatus.ERROR, None, fetched, None, str(exc)
            )

"""Historical OHLCV providers, normalization, and durable SQLite ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Callable, Optional, Union
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select

from data.csv_reader import DuplicatePolicy, read_market_csv
from data.validation import DataValidationError, validate_market_data
from database.models import MarketBar
from data.symbols import a_share_code, normalize_symbol


class HistoricalDataError(ValueError):
    """Raised when historical data cannot be fetched or persisted safely."""


class HistoricalFetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class BarStatus(str, Enum):
    FINAL = "FINAL"
    INTRADAY = "INTRADAY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HistoricalFetchResult:
    frame: pd.DataFrame
    status: HistoricalFetchStatus
    source: str
    fetched_at: datetime
    bar_status: BarStatus = BarStatus.UNKNOWN
    primary_error: Optional[str] = None
    transport: str = "http"
    upstream: str = "unknown"


class HistoricalDataProvider(ABC):
    source = "unknown"

    @abstractmethod
    def fetch(
        self, symbol: str, start: Optional[object] = None, end: Optional[object] = None
    ) -> pd.DataFrame:
        """Return normalized-compatible OHLCV rows for one symbol."""

    def fetch_result(
        self, symbol: str, start: Optional[object] = None, end: Optional[object] = None
    ) -> HistoricalFetchResult:
        fetched_at = datetime.now(timezone.utc)
        try:
            frame = self.fetch(symbol, start, end)
        except HistoricalDataError:
            raise
        except (OSError, ValueError) as exc:
            raise HistoricalDataError(str(exc)) from exc
        status = HistoricalFetchStatus.SUCCESS if not frame.empty else HistoricalFetchStatus.EMPTY
        return HistoricalFetchResult(frame, status, self.source, fetched_at)


def _a_share_symbol(symbol: str) -> str:
    try:
        return a_share_code(symbol)
    except ValueError as exc:
        raise HistoricalDataError(str(exc)) from exc


def _bar_status_for_date(value: str) -> BarStatus:
    try:
        row_date = date.fromisoformat(value[:10])
    except ValueError:
        return BarStatus.UNKNOWN
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return BarStatus.INTRADAY if row_date >= today else BarStatus.FINAL


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["symbol", "datetime", "open", "high", "low", "close", "volume"]
    )


class EastmoneyHistoricalDataProvider(HistoricalDataProvider):
    """Fetch daily bars from Eastmoney's public historical endpoint."""

    source = "EASTMONEY"
    upstream = "push2his.eastmoney.com"
    endpoint = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    def __init__(self, timeout: int = 15, transport: Optional[Callable[[str], Any]] = None) -> None:
        self.timeout = timeout
        self.transport = transport

    def fetch(self, symbol, start=None, end=None) -> pd.DataFrame:
        return self.fetch_result(symbol, start, end).frame

    def fetch_result(self, symbol, start=None, end=None) -> HistoricalFetchResult:
        normalized = _a_share_symbol(symbol)
        fetched_at = datetime.now(timezone.utc)
        market = "1" if normalized.startswith("6") else "0"
        params = {
            "secid": f"{market}.{normalized}",
            "klt": "101",
            "fqt": "1",
            "beg": pd.to_datetime(start, utc=True).strftime("%Y%m%d") if start else "0",
            "end": pd.to_datetime(end, utc=True).strftime("%Y%m%d") if end else "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        url = self.endpoint + "?" + urllib.parse.urlencode(params)
        try:
            if self.transport is not None:
                raw = self.transport(url)
                payload = json.loads(raw) if isinstance(raw, str) else raw
            else:
                request = urllib.request.Request(url, headers={"User-Agent": "quant-trading-system/1.0"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (403, 404, 429, 503):
                return HistoricalFetchResult(
                    _empty_frame(), HistoricalFetchStatus.UNAVAILABLE,
                    self.source, fetched_at, primary_error=str(exc), upstream=self.upstream,
                )
            raise HistoricalDataError(f"Eastmoney {HistoricalFetchStatus.ERROR.value}: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise HistoricalDataError(f"Eastmoney {HistoricalFetchStatus.ERROR.value}: {exc}") from exc
        rows = ((payload.get("data") or {}).get("klines") or []) if isinstance(payload, dict) else []
        if not rows:
            return HistoricalFetchResult(
                _empty_frame(),
                HistoricalFetchStatus.EMPTY,                 self.source, fetched_at, upstream=self.upstream,
            )
        records = []
        for row in rows:
            fields = str(row).split(",")
            if len(fields) < 6:
                raise HistoricalDataError("Eastmoney ERROR: malformed kline row")
            records.append([normalized, fields[0], fields[1], fields[3], fields[4], fields[2], fields[5]])
        frame = pd.DataFrame(records, columns=["symbol", "datetime", "open", "high", "low", "close", "volume"])
        return HistoricalFetchResult(frame, HistoricalFetchStatus.SUCCESS, self.source, fetched_at,
                                     _bar_status_for_date(records[-1][1]), upstream=self.upstream)


class SinaHistoricalDataProvider(HistoricalDataProvider):
    """Fetch daily bars from Sina's public historical endpoint."""

    source = "SINA"
    upstream = "quotes.sina.cn"
    endpoint = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
        "var%20_data=/CN_MarketData.getKLineData"
    )

    def __init__(self, timeout: int = 15, transport: Optional[Callable[[str], Any]] = None) -> None:
        self.timeout = timeout
        self.transport = transport

    def fetch(self, symbol, start=None, end=None) -> pd.DataFrame:
        return self.fetch_result(symbol, start, end).frame

    def fetch_result(self, symbol, start=None, end=None) -> HistoricalFetchResult:
        normalized = _a_share_symbol(symbol)
        market = "sz" if normalized.startswith(("0", "3")) else "sh"
        params = {"symbol": market + normalized, "scale": "240", "ma": "no", "datalen": "1024"}
        fetched_at = datetime.now(timezone.utc)
        url = self.endpoint + "?" + urllib.parse.urlencode(params)
        try:
            if self.transport is not None:
                raw = self.transport(url)
                raw = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            else:
                request = urllib.request.Request(url, headers={"User-Agent": "quant-trading-system/1.0"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
            payload = json.loads(raw[raw.find("["):raw.rfind("]") + 1])
        except HTTPError as exc:
            if exc.code in (403, 404, 429, 503):
                return HistoricalFetchResult(
                    _empty_frame(), HistoricalFetchStatus.UNAVAILABLE,
                    self.source, fetched_at, primary_error=str(exc), upstream=self.upstream,
                )
            raise HistoricalDataError(f"Sina {HistoricalFetchStatus.ERROR.value}: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise HistoricalDataError(f"Sina {HistoricalFetchStatus.ERROR.value}: {exc}") from exc
        if not payload:
            return HistoricalFetchResult(
                _empty_frame(),
                HistoricalFetchStatus.EMPTY,                 self.source, fetched_at, upstream=self.upstream,
            )
        records = []
        for row in payload:
            if not isinstance(row, dict) or not all(
                row.get(key) is not None
                for key in ("day", "open", "high", "low", "close", "volume")
            ):
                raise HistoricalDataError("Sina ERROR: malformed kline row")
            records.append([
                normalized, row["day"], row["open"], row["high"], row["low"],
                row["close"], row["volume"],
            ])
        frame = pd.DataFrame(records, columns=["symbol", "datetime", "open", "high", "low", "close", "volume"])
        return HistoricalFetchResult(frame, HistoricalFetchStatus.SUCCESS, self.source, fetched_at,
                                     _bar_status_for_date(str(records[-1][1])), upstream=self.upstream)


class PrimaryFallbackHistoricalDataProvider(HistoricalDataProvider):
    """Use Sina only when Eastmoney is unavailable or returns an error."""

    source = "SINA"

    def __init__(self, primary: HistoricalDataProvider, fallback: HistoricalDataProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_result: Optional[HistoricalFetchResult] = None

    def fetch(self, symbol, start=None, end=None) -> pd.DataFrame:
        return self.fetch_result(symbol, start, end).frame

    def fetch_result(self, symbol, start=None, end=None) -> HistoricalFetchResult:
        try:
            result = self.primary.fetch_result(symbol, start, end)
            if result.status is HistoricalFetchStatus.SUCCESS:
                self.last_result = result
                return result
            primary_error = result.primary_error or result.status.value
        except HistoricalDataError as exc:
            primary_error = str(exc)
        try:
            result = self.fallback.fetch_result(symbol, start, end)
        except HistoricalDataError as exc:
            raise HistoricalDataError(
                f"primary failed: {primary_error}; fallback failed: {exc}"
            ) from exc
        self.last_result = HistoricalFetchResult(
            result.frame, result.status, result.source, result.fetched_at,
            result.bar_status, str(primary_error), result.transport, result.upstream,
        )
        return self.last_result


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
        result = frame[frame["symbol"] == normalize_symbol(symbol)].copy()
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
        self.last_result: Optional[HistoricalFetchResult] = None

    def update(
        self, symbol: str, start: Optional[object] = None, end: Optional[object] = None
    ) -> int:
        fetched_at = datetime.now(timezone.utc)
        normalized_symbol = normalize_symbol(symbol)
        if start is None:
            with self.database.session() as session:
                latest = session.scalar(
                    select(MarketBar.datetime)
                    .where(MarketBar.symbol == normalized_symbol)
                    .order_by(MarketBar.datetime.desc())
                    .limit(1)
                )
            if latest is not None:
                start = latest
        try:
            result = self.provider.fetch_result(symbol, start, end)
            self.last_result = result
            if result.status is HistoricalFetchStatus.EMPTY or result.frame.empty:
                return 0
            frame = validate_market_data(result.frame)
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
                    "source": result.source, "fetched_at": result.fetched_at,
                    "bar_status": _bar_status_for_date(row["datetime"].isoformat()).value,
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
                query = query.where(MarketBar.symbol == normalize_symbol(symbol))
            return list(session.scalars(query))

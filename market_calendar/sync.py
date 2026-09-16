"""Trading calendar synchronization primitives.

The sync layer is deliberately separated from MarketCalendar so that
remote data sources can be replaced without changing calendar consumers.
"""

from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Iterable, List
from urllib.request import Request, urlopen


class CalendarProvider(ABC):
    """Interface implemented by remote trading-calendar providers."""

    @abstractmethod
    def fetch_trading_days(self, year: int) -> List[date]:
        """Return explicitly confirmed A-share trading days for one year."""
        raise NotImplementedError


class JsonCalendarProvider(CalendarProvider):
    """Generic JSON provider.

    The endpoint is expected to return either:
    1. ["20260105", "20260106", ...]
    2. {"data": ["20260105", "20260106", ...]}

    This intentionally does not hard-code a commercial data vendor.
    """

    def __init__(self, url_template: str, timeout: int = 15) -> None:
        self.url_template = url_template
        self.timeout = timeout

    def fetch_trading_days(self, year: int) -> List[date]:
        url = self.url_template.format(year=year)
        request = Request(
            url,
            headers={"User-Agent": "quant-trading-system/1.0"},
        )

        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if isinstance(payload, dict):
            payload = payload.get("data")

        if not isinstance(payload, list):
            raise ValueError("calendar provider returned an invalid payload")

        days: List[date] = []
        for raw_date in payload:
            parsed = date.fromisoformat(
                str(raw_date).replace("-", "")[:4]
                + "-"
                + str(raw_date).replace("-", "")[4:6]
                + "-"
                + str(raw_date).replace("-", "")[6:8]
            )
            days.append(parsed)

        return sorted(set(days))


class TushareCalendarProvider(CalendarProvider):
    """Tushare Pro implementation of the A-share trading calendar."""

    def __init__(self, token: str | None = None, client=None) -> None:
        if client is not None:
            self.client = client
            return

        if not token:
            raise ValueError("Tushare token is required")

        import tushare as ts

        self.client = ts.pro_api(token)

    def fetch_trading_days(self, year: int) -> List[date]:
        frame = self.client.trade_cal(
            exchange="SSE",
            start_date=f"{year}0101",
            end_date=f"{year}1231",
        )

        if frame is None or len(frame) == 0:
            return []

        days: List[date] = []

        for _, row in frame.iterrows():
            if int(row["is_open"]) != 1:
                continue

            raw_date = str(row["cal_date"])
            days.append(
                date(
                    int(raw_date[:4]),
                    int(raw_date[4:6]),
                    int(raw_date[6:8]),
                )
            )

        return sorted(set(days))


class CalendarSyncService:
    """Synchronize remote calendar data into the local CSV format."""

    def __init__(self, provider: CalendarProvider) -> None:
        self.provider = provider

    def sync_year(self, year: int, output_path: str | Path) -> Path:
        trading_days = self.provider.fetch_trading_days(year)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        trading_day_set = set(trading_days)

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "is_open"])

            start = date(year, 1, 1)
            end = date(year, 12, 31)

            current = start
            while current <= end:
                writer.writerow(
                    [
                        current.isoformat(),
                        "1" if current in trading_day_set else "0",
                    ]
                )
                current = current.fromordinal(current.toordinal() + 1)

        return output

    def sync_years(self, years: Iterable[int], output_path: str | Path) -> Path:
        """Synchronize multiple years into one local calendar CSV."""
        normalized_years = sorted(set(int(year) for year in years))

        if not normalized_years:
            raise ValueError("years must not be empty")

        all_trading_days = set()

        for year in normalized_years:
            all_trading_days.update(self.provider.fetch_trading_days(year))

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        start = date(normalized_years[0], 1, 1)
        end = date(normalized_years[-1], 12, 31)

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "is_open"])

            current = start
            while current <= end:
                writer.writerow(
                    [
                        current.isoformat(),
                        "1" if current in all_trading_days else "0",
                    ]
                )
                current = current.fromordinal(current.toordinal() + 1)

        return output

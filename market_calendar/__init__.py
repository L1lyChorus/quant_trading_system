"""A-share calendar primitives, deliberately conservative about unknown dates."""

from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Union
from zoneinfo import ZoneInfo

import pandas as pd


SHANGHAI = ZoneInfo("Asia/Shanghai")


class MarketSession(str, Enum):
    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"
    PRE_OPEN = "PRE_OPEN"
    AUCTION = "AUCTION"
    TRADING = "TRADING"
    MIDDAY_BREAK = "MIDDAY_BREAK"
    AFTER_HOURS = "AFTER_HOURS"
    HOLIDAY = "HOLIDAY"
    WEEKEND = "WEEKEND"
    # Compatibility with the stage-8 API; new code should use CLOSED/WEEKEND.
    MARKET_CLOSED = "WEEKEND"


class MarketCalendar:
    """A date-level calendar loaded from a trusted/exported calendar dataset.

    A missing weekday is UNKNOWN, never implicitly a trading day.
    """

    def __init__(self, trading_days: Optional[Dict[date, bool]] = None) -> None:
        self._days = dict(trading_days or {})

    @classmethod
    def from_csv(cls, path: Union[str, Path]) -> "MarketCalendar":
        frame = pd.read_csv(path)
        if "date" not in frame.columns or "is_open" not in frame.columns:
            raise ValueError("calendar CSV requires date and is_open columns")
        days: Dict[date, bool] = {}
        for raw_date, raw_open in zip(frame["date"], frame["is_open"]):
            parsed = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(parsed):
                raise ValueError("calendar date is invalid")
            days[parsed.date()] = str(raw_open).strip().lower() in {"1", "true", "open"}
        return cls(days)

    def is_trading_day(self, value: Union[date, datetime]) -> bool:
        day = value.date() if isinstance(value, datetime) else value
        return day.weekday() < 5 and self._days.get(day, False)

    def knows(self, value: Union[date, datetime]) -> bool:
        day = value.date() if isinstance(value, datetime) else value
        return day in self._days


def is_trading_day(
    value: Union[date, datetime], calendar: Optional[MarketCalendar] = None
) -> bool:
    """Return true only for an explicitly known open date."""
    if isinstance(value, datetime):
        value = value.date()
    if value.weekday() >= 5:
        return False
    return calendar.is_trading_day(value) if calendar is not None else False


def session_status(
    value: datetime, calendar: Optional[MarketCalendar] = None
) -> MarketSession:
    """Classify a time window separately from date-level calendar knowledge.

    The optional calendar is required to distinguish TRADING from UNKNOWN.
    Without it, the legacy schedule-only behavior is retained for quote
    freshness callers; callers making trading decisions must use a calendar.
    """
    local = value.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return MarketSession.WEEKEND
    if calendar is not None and not calendar.knows(local.date()):
        return MarketSession.UNKNOWN
    if calendar is not None and not calendar.is_trading_day(local.date()):
        return MarketSession.HOLIDAY
    current = local.time()
    if time(9, 15) <= current < time(9, 30):
        return MarketSession.AUCTION
    if time(9, 30) <= current < time(11, 30) or time(13, 0) <= current < time(15, 0):
        return MarketSession.TRADING
    if current < time(9, 15):
        return MarketSession.PRE_OPEN
    if time(11, 30) <= current < time(13, 0):
        return MarketSession.MIDDAY_BREAK
    return MarketSession.AFTER_HOURS

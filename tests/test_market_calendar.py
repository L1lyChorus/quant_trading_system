"""Tests for explicit date knowledge and session classification."""

from datetime import date, datetime, timezone

from market_calendar import MarketCalendar, MarketSession, is_trading_day, session_status


def test_unknown_weekday_is_not_trading():
    day = date(2024, 1, 2)
    calendar = MarketCalendar()
    assert not is_trading_day(day, calendar)
    assert session_status(datetime(2024, 1, 2, 2, tzinfo=timezone.utc), calendar) == MarketSession.UNKNOWN


def test_known_holiday_and_known_trading_day():
    calendar = MarketCalendar({date(2024, 1, 1): False, date(2024, 1, 2): True})
    assert session_status(datetime(2024, 1, 1, 3, tzinfo=timezone.utc), calendar) == MarketSession.HOLIDAY
    assert is_trading_day(date(2024, 1, 2), calendar)
    assert session_status(datetime(2024, 1, 2, 2, tzinfo=timezone.utc), calendar) == MarketSession.TRADING

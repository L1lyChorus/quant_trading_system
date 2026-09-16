from datetime import date

import pandas as pd

from market_calendar.sync import CalendarProvider, TushareCalendarProvider


class FakeTusharePro:
    def __init__(self):
        self.last_kwargs = None

    def trade_cal(self, **kwargs):
        self.last_kwargs = kwargs
        return pd.DataFrame(
            [
                {"cal_date": "20260102", "is_open": 1},
                {"cal_date": "20260103", "is_open": 0},
                {"cal_date": "20260105", "is_open": 1},
            ]
        )


def test_tushare_calendar_provider_returns_open_days():
    provider = TushareCalendarProvider(client=FakeTusharePro())

    result = provider.fetch_trading_days(2026)

    assert result == [
        date(2026, 1, 2),
        date(2026, 1, 5),
    ]


def test_tushare_calendar_provider_queries_sse_and_requested_year():
    client = FakeTusharePro()
    provider = TushareCalendarProvider(client=client)

    provider.fetch_trading_days(2026)

    assert client.last_kwargs == {
        "exchange": "SSE",
        "start_date": "20260101",
        "end_date": "20261231",
    }

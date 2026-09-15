from datetime import date

from market_calendar.sync import CalendarProvider, CalendarSyncService, JsonCalendarProvider


class FakeCalendarProvider(CalendarProvider):
    def fetch_trading_days(self, year: int):
        return [
            date(year, 1, 2),
            date(year, 1, 3),
            date(year, 1, 3),
        ]


def test_json_calendar_provider_parses_list(monkeypatch):
    class FakeResponse:
        def read(self):
            return b'["20260102", "20260103", "20260103"]'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "market_calendar.sync.urlopen",
        lambda request, timeout: FakeResponse(),
    )

    provider = JsonCalendarProvider("https://example.com/{year}")
    result = provider.fetch_trading_days(2026)

    assert result == [date(2026, 1, 2), date(2026, 1, 3)]


def test_json_calendar_provider_parses_data_object(monkeypatch):
    class FakeResponse:
        def read(self):
            return b'{"data": ["20260105", "20260106"]}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(
        "market_calendar.sync.urlopen",
        lambda request, timeout: FakeResponse(),
    )

    provider = JsonCalendarProvider("https://example.com/{year}")
    result = provider.fetch_trading_days(2026)

    assert result == [date(2026, 1, 5), date(2026, 1, 6)]


def test_sync_service_writes_full_year_calendar(tmp_path):
    output = tmp_path / "calendar.csv"

    service = CalendarSyncService(FakeCalendarProvider())
    result = service.sync_year(2026, output)

    assert result == output
    assert output.exists()

    lines = output.read_text(encoding="utf-8").splitlines()

    assert lines[0] == "date,is_open"
    assert len(lines) == 365 + 1
    assert "2026-01-02,1" in lines
    assert "2026-01-03,1" in lines
    assert "2026-01-04,0" in lines

def test_synced_calendar_can_be_loaded_by_market_calendar(tmp_path):
    from market_calendar import MarketCalendar

    output = tmp_path / "calendar.csv"

    service = CalendarSyncService(FakeCalendarProvider())
    service.sync_year(2026, output)

    calendar = MarketCalendar.from_csv(output)

    assert calendar.knows(date(2026, 1, 2))
    assert calendar.is_trading_day(date(2026, 1, 2))
    assert calendar.knows(date(2026, 1, 4))
    assert not calendar.is_trading_day(date(2026, 1, 4))

class MultiYearFakeCalendarProvider(CalendarProvider):
    def __init__(self):
        self.calls = []

    def fetch_trading_days(self, year: int):
        self.calls.append(year)
        return [date(year, 1, 2)]


def test_sync_years_combines_multiple_years(tmp_path):
    output = tmp_path / "calendar.csv"
    provider = MultiYearFakeCalendarProvider()
    service = CalendarSyncService(provider)

    result = service.sync_years([2025, 2026], output)

    assert result == output
    assert provider.calls == [2025, 2026]

    lines = output.read_text(encoding="utf-8").splitlines()

    assert "2025-01-02,1" in lines
    assert "2026-01-02,1" in lines
    assert len(lines) == 365 + 365 + 1

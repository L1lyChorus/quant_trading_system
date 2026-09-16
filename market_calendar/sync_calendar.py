import os

from dotenv import load_dotenv

from .sync import CalendarSyncService, TushareCalendarProvider


def main() -> None:
    load_dotenv()

    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is not configured")

    provider = TushareCalendarProvider(token=token)
    service = CalendarSyncService(provider)

    output = service.sync_years(
        years=[2026],
        output_path="data/calendar/2026.csv",
    )

    print(f"Calendar synced to: {output}")


if __name__ == "__main__":
    main()


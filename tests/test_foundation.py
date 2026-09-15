"""Smoke tests for the Step 1 foundation."""

from sqlalchemy import create_engine, inspect, text

from config.settings import Settings
from database.connection import initialize_database


def test_live_trading_is_disabled_by_default() -> None:
    assert Settings().live_trading_enabled is False


def test_database_initialization_creates_foundation_tables(tmp_path) -> None:
    database = initialize_database(f"sqlite:///{tmp_path / 'smoke.db'}")
    inspector = inspect(database.engine)
    tables = set(inspector.get_table_names())
    assert {"accounts", "orders", "executions", "positions"} <= tables

    account_columns = {
        column["name"]: column for column in inspector.get_columns("accounts")
    }
    assert {"initial_cash", "current_cash"} <= account_columns.keys()
    assert account_columns["initial_cash"]["nullable"] is False
    assert account_columns["current_cash"]["nullable"] is False


def test_existing_market_bars_schema_gets_bar_status_migration(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    engine = create_engine("sqlite:///" + str(path))
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE market_bars ("
                "id INTEGER PRIMARY KEY, symbol VARCHAR(32) NOT NULL, "
                "datetime DATETIME NOT NULL, open NUMERIC NOT NULL, "
                "high NUMERIC NOT NULL, low NUMERIC NOT NULL, "
                "close NUMERIC NOT NULL, volume NUMERIC NOT NULL, "
                "source VARCHAR(200) NOT NULL, fetched_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO market_bars "
                "(id, symbol, datetime, open, high, low, close, volume, source, fetched_at) "
                "VALUES (1, '600000', '2024-01-01 00:00:00', 1, 1, 1, 1, 1, 'LEGACY', "
                "'2024-01-01 00:00:00')"
            )
        )

    database = initialize_database("sqlite:///" + str(path))
    columns = {
        column["name"]: column
        for column in inspect(database.engine).get_columns("market_bars")
    }
    assert columns["bar_status"]["nullable"] is False
    with database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT bar_status FROM market_bars")
        ).fetchall() == [("UNKNOWN",)]

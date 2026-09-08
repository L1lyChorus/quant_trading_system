"""Smoke tests for the Step 1 foundation."""

from sqlalchemy import inspect

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
    assert {"initial_funds", "current_cash"} <= account_columns.keys()
    assert account_columns["initial_funds"]["nullable"] is False
    assert account_columns["current_cash"]["nullable"] is False

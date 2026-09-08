"""Paper Trading account, order, execution, and transaction tests."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from database.connection import initialize_database
from database.models import Account, Execution, Order, OrderStatus, Position
from trading.service import PaperTradingService


@pytest.fixture
def database(tmp_path):
    database = initialize_database("sqlite:///" + str(tmp_path / "paper.db"))
    return database


@pytest.fixture
def account(database):
    with database.session() as session:
        return PaperTradingService(session).create_default_account(Decimal("1000"))


def test_default_account_is_created_and_read_back(database):
    with database.session() as session:
        created = PaperTradingService(session).create_default_account(Decimal("1000"))
    with database.session() as session:
        loaded = session.get(Account, created.id)
        assert loaded.initial_cash == Decimal("1000.00000000")
        assert loaded.current_cash == Decimal("1000.00000000")
        assert loaded.created_at is not None
        assert loaded.updated_at is not None


def test_initial_cash_cannot_be_overwritten_by_repeated_default_creation(database):
    with database.session() as session:
        service = PaperTradingService(session)
        first = service.create_default_account(Decimal("1000"))
        second = service.create_default_account(Decimal("500"))
        assert second.id == first.id
        assert second.initial_cash == Decimal("1000")


def test_buy_updates_cash_commission_position_and_average_cost(database, account):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "aapl", "BUY", Decimal("2"), Decimal("100")
        )
    with database.session() as session:
        loaded = session.get(Account, account.id)
        position = session.scalar(select(Position).where(Position.account_id == account.id))
        assert result.order.status == OrderStatus.FILLED
        assert result.execution.commission == Decimal("0.20000000")
        assert loaded.current_cash == Decimal("799.80000000")
        assert position.quantity == Decimal("2.00000000")
        assert position.average_cost == Decimal("100.10000000")


def test_buy_fails_with_insufficient_cash_and_does_not_change_account(database, account):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "BUY", Decimal("20"), Decimal("100")
        )
        assert result.order.status == OrderStatus.REJECTED
        assert result.order.rejection_reason == "insufficient cash"
    with database.session() as session:
        assert session.get(Account, account.id).current_cash == Decimal("1000")
        assert session.scalar(select(Position).where(Position.account_id == account.id)) is None


def test_sell_updates_cash_position_and_realized_pnl(database, account):
    with database.session() as session:
        PaperTradingService(session).execute_trade(
            account.id, "AAPL", "BUY", Decimal("2"), Decimal("100")
        )
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "SELL", Decimal("1"), Decimal("110")
        )
    with database.session() as session:
        loaded = session.get(Account, account.id)
        position = session.scalar(select(Position).where(Position.account_id == account.id))
        assert loaded.current_cash == Decimal("909.69000000")
        assert position.quantity == Decimal("1.00000000")
        assert result.realized_pnl == Decimal("9.79000000")


def test_full_sell_deletes_position_to_keep_holdings_analysis_clean(database, account):
    with database.session() as session:
        PaperTradingService(session).execute_trade(
            account.id, "AAPL", "BUY", Decimal("1"), Decimal("100")
        )
        PaperTradingService(session).execute_trade(
            account.id, "AAPL", "SELL", Decimal("1"), Decimal("100")
        )
    with database.session() as session:
        assert session.scalar(select(Position).where(Position.account_id == account.id)) is None


def test_sell_fails_with_insufficient_position(database, account):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "SELL", Decimal("1"), Decimal("100")
        )
        assert result.order.status == OrderStatus.REJECTED
        assert result.order.rejection_reason == "insufficient position"


def test_order_execution_relationship_and_fields(database, account):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "BUY", Decimal("1"), Decimal("50"), signal_id="sig-1"
        )
        order = session.get(Order, result.order.id)
        execution = session.get(Execution, result.execution.id)
        assert execution.order_id == order.id
        assert execution.symbol == order.symbol == "AAPL"
        assert order.signal_id == "sig-1"


@pytest.mark.parametrize(
    "quantity, price, reason",
    [(Decimal("0"), Decimal("10"), "quantity"), (Decimal("1"), Decimal("0"), "price")],
)
def test_invalid_buy_is_rejected_without_changes(database, account, quantity, price, reason):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "BUY", quantity, price
        )
        assert result.order.status == OrderStatus.REJECTED
        assert reason in result.order.rejection_reason


def test_invalid_side_is_rejected(database, account):
    with database.session() as session:
        result = PaperTradingService(session).execute_trade(
            account.id, "AAPL", "HOLD", Decimal("1"), Decimal("10")
        )
        assert result.order.status == OrderStatus.REJECTED
        assert "BUY or SELL" in result.order.rejection_reason


def test_transaction_failure_rolls_back_all_trade_records(database, account, monkeypatch):
    with database.session() as session:
        service = PaperTradingService(session)
        original_cash = session.get(Account, account.id).current_cash

        def fail_execution(execution):
            raise RuntimeError("injected execution failure")

        monkeypatch.setattr(service.repository, "add_execution", fail_execution)
        with pytest.raises(RuntimeError, match="injected"):
            service.execute_trade(
                account.id, "AAPL", "BUY", Decimal("1"), Decimal("10")
            )
        assert session.get(Account, account.id).current_cash == original_cash
        assert session.scalar(select(func.count(Order.id))) == 0
        assert session.scalar(select(func.count(Execution.id))) == 0
        assert session.scalar(select(func.count(Position.id))) == 0

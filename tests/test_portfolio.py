"""Portfolio snapshot tests."""

from decimal import Decimal

import pytest

from database.connection import initialize_database
from database.models import Position
from portfolio.service import PortfolioService
from trading.service import PaperTradingService


@pytest.fixture
def database(tmp_path):
    return initialize_database("sqlite:///" + str(tmp_path / "portfolio.db"))


@pytest.fixture
def account(database):
    with database.session() as session:
        return PaperTradingService(session).create_default_account(
            Decimal("100000")
        )


def test_portfolio_snapshot_calculates_value_and_weight(database, account):
    with database.session() as session:
        position = Position(
            account_id=account.id,
            symbol="600000",
            quantity=Decimal("1000"),
            average_cost=Decimal("28"),
        )
        session.add(position)
        session.commit()

    with database.session() as session:
        snapshot = PortfolioService(session).snapshot(
            account.id,
            {"600000": Decimal("35")},
        )

    assert snapshot.cash == Decimal("100000")
    assert snapshot.market_value == Decimal("35000")
    assert snapshot.portfolio_value == Decimal("135000")
    assert snapshot.exposure == Decimal("35000") / Decimal("135000")

    position_snapshot = snapshot.positions["600000.SH"]

    assert position_snapshot.quantity == Decimal("1000")
    assert position_snapshot.market_price == Decimal("35")
    assert position_snapshot.market_value == Decimal("35000")
    assert position_snapshot.unrealized_pnl == Decimal("7000")
    assert position_snapshot.weight == Decimal("35000") / Decimal("135000")


def test_portfolio_snapshot_requires_market_price(database, account):
    with database.session() as session:
        position = Position(
            account_id=account.id,
            symbol="600000",
            quantity=Decimal("100"),
            average_cost=Decimal("20"),
        )
        session.add(position)
        session.commit()

    with database.session() as session:
        with pytest.raises(
            ValueError,
            match="market price is required",
        ):
            PortfolioService(session).snapshot(account.id, {})

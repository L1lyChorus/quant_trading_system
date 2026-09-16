from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from database.models import Account
from portfolio.models import PortfolioSnapshot, PositionSnapshot
from trading.repository import TradingRepository
from data.symbols import normalize_symbol


ZERO = Decimal("0")


class PortfolioService:
    """组合管理服务。

    基于现有 Account 和 Position 数据计算组合状态，
    不创建新的持仓或账户数据库模型。
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TradingRepository(session)

    def snapshot(
        self,
        account_id: int,
        market_prices: Mapping[str, Decimal],
    ) -> PortfolioSnapshot:
        account = self.repository.get_account(account_id)
        if account is None:
            raise ValueError("account does not exist")

        positions = self.repository.get_positions(account_id)

        normalized_prices = {
            normalize_symbol(symbol): Decimal(price)
            for symbol, price in market_prices.items()
        }

        cash = Decimal(account.current_cash)
        position_snapshots = {}

        total_market_value = ZERO

        for position in positions:
            symbol = normalize_symbol(position.symbol)

            if symbol not in normalized_prices:
                raise ValueError(
                    f"market price is required for position: {symbol}"
                )

            market_price = normalized_prices[symbol]

            if market_price <= ZERO:
                raise ValueError(
                    f"market price must be greater than 0: {symbol}"
                )

            quantity = Decimal(position.quantity)
            average_cost = Decimal(position.average_cost)
            market_value = quantity * market_price
            unrealized_pnl = (
                market_price - average_cost
            ) * quantity

            total_market_value += market_value

            position_snapshots[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
                market_price=market_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                weight=ZERO,
            )

        portfolio_value = cash + total_market_value

        if portfolio_value > ZERO:
            exposure = total_market_value / portfolio_value

            weighted_positions = {}

            for symbol, position in position_snapshots.items():
                weighted_positions[symbol] = PositionSnapshot(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    average_cost=position.average_cost,
                    market_price=position.market_price,
                    market_value=position.market_value,
                    unrealized_pnl=position.unrealized_pnl,
                    weight=position.market_value / portfolio_value,
                )

            position_snapshots = weighted_positions
        else:
            exposure = ZERO

        return PortfolioSnapshot(
            account_id=account_id,
            cash=cash,
            market_value=total_market_value,
            portfolio_value=portfolio_value,
            exposure=exposure,
            positions=position_snapshots,
        )

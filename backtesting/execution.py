"""In-memory execution adapter for backtests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from backtesting.models import (
    BacktestConfig,
    BacktestExecution,
    BacktestOrder,
    BacktestPortfolio,
)
from strategies.signals import SignalAction


class BacktestExecutionAdapter:
    """Apply next-bar-open fills without using PaperTradingService or SQLite."""

    def __init__(self, config: BacktestConfig, portfolio: BacktestPortfolio) -> None:
        self.config = config
        self.portfolio = portfolio

    def execute(
        self,
        action: SignalAction,
        signal_time: datetime,
        execution_time: datetime,
        open_price: Decimal,
        quantity: Decimal,
        reason: str,
    ):
        side = action.value
        fill_price = open_price + self.config.slippage if action == SignalAction.BUY else open_price - self.config.slippage
        fee = fill_price * quantity * self.config.commission_rate
        order = BacktestOrder(
            str(uuid4()), self.config.symbol, side, quantity, signal_time,
            execution_time, "FILLED", reason,
        )
        if action == SignalAction.BUY:
            self.portfolio.apply_buy(quantity, fill_price, fee)
        else:
            realized_pnl = self.portfolio.apply_sell(quantity, fill_price, fee)
        execution = BacktestExecution(
            str(uuid4()), order.order_id, self.config.symbol, side, quantity,
            fill_price, fee, execution_time,
        )
        return order, execution, (realized_pnl if action == SignalAction.SELL else Decimal("0"))

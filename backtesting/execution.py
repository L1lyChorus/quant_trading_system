"""In-memory execution adapter for backtests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from backtesting.models import (
    BacktestConfig,
    BacktestExecution,
    BacktestOrder,
    BacktestPortfolio,
    BacktestOrderStatus,
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
        sequence: int,
        symbol: str = "",
    ):
        symbol = symbol or self.config.symbol
        side = action.value
        if open_price <= 0:
            raise ValueError("execution price must be greater than 0")
        multiplier = (
            Decimal("1") + self.config.slippage
            if action == SignalAction.BUY
            else Decimal("1") - self.config.slippage
        )
        if multiplier <= 0:
            raise ValueError("slippage results in a non-positive execution price")
        fill_price = open_price * multiplier
        fee = fill_price * quantity * self.config.commission_rate
        order = BacktestOrder(
            "backtest-order-{}".format(sequence), symbol, side, quantity,
            signal_time, execution_time, BacktestOrderStatus.FILLED, reason,
        )
        if action == SignalAction.BUY:
            self.portfolio.apply_buy_for(symbol, quantity, fill_price, fee)
        else:
            realized_pnl = self.portfolio.apply_sell_for(symbol, quantity, fill_price, fee)
        execution = BacktestExecution(
            "backtest-execution-{}".format(sequence), order.order_id,
            symbol, side, quantity,
            fill_price, fee, execution_time,
        )
        return order, execution, (realized_pnl if action == SignalAction.SELL else Decimal("0"))

    def cancel(self, action, signal_time, reason, sequence, symbol=""):
        symbol = symbol or self.config.symbol
        return BacktestOrder(
            "backtest-order-{}".format(sequence), symbol, action.value,
            self.config.quantity, signal_time, signal_time,
            BacktestOrderStatus.CANCELLED, reason,
        )

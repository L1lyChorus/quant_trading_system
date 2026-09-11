"""Leak-free single-symbol daily-bar backtest engine."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd

from backtesting.execution import BacktestExecutionAdapter
from backtesting.models import (
    BacktestConfig,
    BacktestOrder,
    BacktestPortfolio,
    BacktestResult,
    BacktestMetrics,
    ClosedTrade,
    EquityPoint,
    BacktestOrderStatus,
)
from data.service import MarketDataService
from data.validation import validate_market_data
from risk_management.evaluator import RiskEvaluator
from strategies.base import Strategy
from strategies.signals import SignalAction


class BacktestEngine:
    """Generate signals from visible history and fill them one bar later."""

    def __init__(
        self,
        market_data: MarketDataService,
        strategy: Strategy,
        risk_evaluator: Optional[RiskEvaluator] = None,
    ) -> None:
        self.market_data = market_data
        self.strategy = strategy
        self.risk_evaluator = risk_evaluator or RiskEvaluator()

    def run(self, config: BacktestConfig) -> BacktestResult:
        frames = {}
        for symbol in config.symbols:
            frames[symbol] = self._frame(
                self.market_data.get_historical_bars(
                    symbol, config.start_date, config.end_date, config.finalized_only
                ),
                config.finalized_only,
            )
        timeline = sorted({
            row["datetime"]
            for frame in frames.values()
            for _, row in frame.iterrows()
        })
        portfolio = BacktestPortfolio(config.initial_cash)
        adapter = BacktestExecutionAdapter(config, portfolio)
        orders: List[BacktestOrder] = []
        executions = []
        rejected = []
        equity_curve = []
        visible_timestamps = []
        closed_trades = []
        entries = {}
        sequence = 0
        self._pending = []

        for timestamp_value in timeline:
            timestamp = timestamp_value.to_pydatetime()
            pending = [
                item for item in getattr(self, "_pending", [])
                if item[0] == timestamp_value
            ]
            self._pending = [item for item in getattr(self, "_pending", []) if item[0] != timestamp_value]
            for _, symbol, signal, signal_time, sequence_number in pending:
                row = frames[symbol][frames[symbol]["datetime"] == timestamp_value].iloc[0]
                next_open = Decimal(str(row["open"]))
                risk = self.risk_evaluator.evaluate_trade(
                    {"current_cash": portfolio.cash}, symbol, signal.action.value,
                    config.quantity, next_open,
                    {name: portfolio.quantity_for(name) for name in config.symbols},
                )
                if not risk.allowed:
                    rejected.append({
                        "signal_id": signal.signal_id, "timestamp": signal_time,
                        "action": signal.action.value, "reasons": list(risk.reasons),
                    })
                    continue
                order, execution, realized_pnl = adapter.execute(
                    signal.action, signal_time, timestamp, next_open,
                    config.quantity, signal.reason, sequence_number, symbol,
                )
                orders.append(order)
                executions.append(execution)
                if signal.action == SignalAction.BUY:
                    entries[symbol] = (execution.executed_at, execution.price)
                elif signal.action == SignalAction.SELL and symbol in entries:
                    entry_time, entry_price = entries.pop(symbol)
                    closed_trades.append(ClosedTrade(
                        symbol, "BUY_SELL", execution.quantity, entry_time,
                        execution.executed_at, entry_price, execution.price, realized_pnl,
                    ))

            marks = {}
            for symbol, frame in frames.items():
                visible_rows = frame[frame["datetime"] <= timestamp_value]
                if visible_rows.empty:
                    continue
                row = visible_rows.iloc[-1]
                marks[symbol] = Decimal(str(row["close"]))
            total_value = portfolio.total_market_value(marks)
            first_mark = next(iter(marks.values()), Decimal("0"))
            visible_timestamps.append(timestamp)
            equity_curve.append(
                EquityPoint(
                    timestamp, first_mark, portfolio.cash,
                    sum(portfolio.positions.values(), Decimal("0")),
                    total_value, portfolio.cash + total_value,
                )
            )
            for symbol in config.symbols:
                frame = frames[symbol]
                visible = frame[frame["datetime"] <= timestamp_value].copy()
                if visible.empty or visible.iloc[-1]["datetime"] != timestamp_value:
                    continue
                signal = self.strategy.generate_signal(
                    visible, symbol, current_position=portfolio,
                    simulation_time=timestamp, cutoff=timestamp,
                )
                if signal.action == SignalAction.HOLD:
                    continue
                sequence += 1
                future = frame[
                    (frame["datetime"] > timestamp_value) &
                    (frame["bar_status"] == "FINAL")
                ]
                if future.empty:
                    orders.append(adapter.cancel(
                        signal.action, timestamp, "no next finalized bar", sequence, symbol
                    ))
                else:
                    self._pending.append((
                        future.iloc[0]["datetime"], symbol, signal, timestamp, sequence
                    ))

        final_equity = equity_curve[-1].total_equity if equity_curve else portfolio.cash
        metrics = self._metrics(config.initial_cash, final_equity, equity_curve, closed_trades)
        return BacktestResult(
            config, config.symbol, config.initial_cash, portfolio.cash, final_equity,
            orders, executions, equity_curve, closed_trades, metrics,
            rejected, visible_timestamps,
            equity_curve[0].timestamp if equity_curve else None,
            equity_curve[-1].timestamp if equity_curve else None,
            len(timeline), len(orders), len(executions),
            sum(1 for order in orders if order.status == BacktestOrderStatus.CANCELLED),
            dict(portfolio.positions),
        )

    @staticmethod
    def _metrics(initial_cash, final_equity, curve, closed_trades):
        initial_cash = Decimal(initial_cash)
        total_return = (
            final_equity / initial_cash - Decimal("1")
            if initial_cash else Decimal("0")
        )
        if len(curve) >= 2:
            days = Decimal(str((curve[-1].timestamp - curve[0].timestamp).total_seconds() / 86400))
        else:
            days = Decimal("0")
        annualized = (
            (final_equity / initial_cash) ** (Decimal("365") / days) - Decimal("1")
            if initial_cash and final_equity >= 0 and days > 0
            else Decimal("0")
        )
        peak = None
        max_drawdown = Decimal("0")
        for point in curve:
            peak = point.total_equity if peak is None else max(peak, point.total_equity)
            if peak and peak > 0:
                max_drawdown = max(max_drawdown, (peak - point.total_equity) / peak)
        wins = sum(1 for trade in closed_trades if trade.pnl > 0)
        losses = sum(1 for trade in closed_trades if trade.pnl < 0)
        gross_wins = sum((trade.pnl for trade in closed_trades if trade.pnl > 0), Decimal("0"))
        gross_losses = sum((-trade.pnl for trade in closed_trades if trade.pnl < 0), Decimal("0"))
        return BacktestMetrics(
            total_return, annualized, max_drawdown, len(closed_trades),
            wins, losses,
            Decimal(wins) / len(closed_trades) if closed_trades else None,
            gross_wins / gross_losses if gross_losses else None,
        )

    @staticmethod
    def _frame(bars: list, finalized_only: bool) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame(
                columns=[
                    "symbol", "datetime", "open", "high", "low", "close",
                    "volume", "bar_status",
                ]
            )
        frame = pd.DataFrame([
            {
                "symbol": bar.symbol, "datetime": bar.datetime,
                "open": bar.open, "high": bar.high, "low": bar.low,
                "close": bar.close, "volume": bar.volume,
                "bar_status": bar.bar_status,
            }
            for bar in bars if not finalized_only or bar.bar_status == "FINAL"
        ])
        if frame.empty:
            return frame
        normalized = validate_market_data(frame)
        normalized = normalized.merge(
            frame[["symbol", "datetime", "bar_status"]],
            on=["symbol", "datetime"],
            how="left",
        )
        return normalized.sort_values("datetime", kind="stable").reset_index(drop=True)

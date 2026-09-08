"""Leak-free single-symbol daily-bar backtest engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional

import pandas as pd

from backtesting.execution import BacktestExecutionAdapter
from backtesting.models import (
    BacktestConfig,
    BacktestOrder,
    BacktestPortfolio,
    BacktestResult,
    EquityPoint,
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
        bars = self.market_data.get_historical_bars(
            config.symbol, config.start_date, config.end_date, True
        )
        frame = self._frame(bars, True)
        portfolio = BacktestPortfolio(config.initial_cash)
        adapter = BacktestExecutionAdapter(config, portfolio)
        orders: List[BacktestOrder] = []
        executions = []
        rejected = []
        equity_curve = []
        visible_timestamps = []

        for index, row in frame.iterrows():
            visible = frame.iloc[: index + 1].copy()
            timestamp = row["datetime"].to_pydatetime()
            visible_timestamps.append(timestamp)
            equity_curve.append(
                EquityPoint(
                    timestamp, Decimal(str(row["close"])), portfolio.cash,
                    portfolio.quantity, portfolio.equity(Decimal(str(row["close"]))),
                )
            )
            if index >= len(frame) - 1:
                continue
            signal = self.strategy.generate_signal(
                visible, config.symbol, current_position=portfolio,
                simulation_time=timestamp, cutoff=timestamp,
            )
            if signal.action == SignalAction.HOLD:
                continue
            next_row = frame.iloc[index + 1]
            next_open = Decimal(str(next_row["open"]))
            risk = self.risk_evaluator.evaluate_trade(
                {"current_cash": portfolio.cash},
                config.symbol,
                signal.action.value,
                config.quantity,
                next_open,
                {config.symbol: portfolio.quantity},
            )
            if not risk.allowed:
                rejected.append({
                    "signal_id": signal.signal_id,
                    "timestamp": timestamp,
                    "action": signal.action.value,
                    "reasons": list(risk.reasons),
                })
                continue
            order, execution, _ = adapter.execute(
                signal.action, timestamp,
                next_row["datetime"].to_pydatetime(),
                next_open, config.quantity, signal.reason,
            )
            orders.append(order)
            executions.append(execution)

        final_price = Decimal(str(frame.iloc[-1]["close"])) if len(frame) else Decimal("0")
        final_equity = portfolio.equity(final_price) if len(frame) else portfolio.cash
        return BacktestResult(
            config.symbol, config.initial_cash, portfolio.cash, final_equity,
            orders, executions, equity_curve, rejected, visible_timestamps,
        )

    @staticmethod
    def _frame(bars: list, finalized_only: bool) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame(
                columns=["symbol", "datetime", "open", "high", "low", "close", "volume"]
            )
        frame = pd.DataFrame([
            {
                "symbol": bar.symbol, "datetime": bar.datetime,
                "open": bar.open, "high": bar.high, "low": bar.low,
                "close": bar.close, "volume": bar.volume,
            }
            for bar in bars if not finalized_only or bar.bar_status == "FINAL"
        ])
        if frame.empty:
            return frame
        return validate_market_data(frame).sort_values(
            "datetime", kind="stable"
        ).reset_index(drop=True)

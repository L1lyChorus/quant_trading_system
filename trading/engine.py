"""Coordination layer between read-only signals, risk, and paper execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from database.models import Account
from risk_management.models import RiskResult
from risk_management.evaluator import RiskEvaluator
from strategies.base import Strategy
from strategies.signals import Signal, SignalAction
from trading.repository import TradingRepository
from trading.service import PaperTradingService, TradeResult
from data.symbols import normalize_symbol


@dataclass(frozen=True)
class TradingRunResult:
    signal: Optional[Signal]
    risk_result: Optional[RiskResult]
    trade_result: Optional[TradeResult]
    status: str
    message: str


class TradingEngine:
    """Run one signal-to-paper-trade cycle without owning business rules."""

    def __init__(
        self,
        session: Session,
        strategy: Strategy,
        risk_evaluator: Optional[RiskEvaluator] = None,
        paper_trading_service: Optional[PaperTradingService] = None,
    ) -> None:
        self.session = session
        self.strategy = strategy
        self.risk_evaluator = risk_evaluator or RiskEvaluator()
        self.paper_trading_service = paper_trading_service or PaperTradingService(session)
        self.repository = TradingRepository(session)

    def run_once(
        self,
        market_data: pd.DataFrame,
        account_id: int,
        symbol: str,
        quantity: Any,
        current_position: Optional[Any] = None,
        simulation_time: Optional[datetime] = None,
        cutoff: Optional[datetime] = None,
        valuation_prices: Optional[Any] = None,
    ) -> TradingRunResult:
        del valuation_prices  # Reserved for future risk valuation extensions.
        try:
            account = self.repository.get_account(account_id)
            positions = self.repository.get_positions(account_id)
            position = (
                current_position
                if current_position is not None
                else self.repository.get_position(account_id, normalize_symbol(symbol))
            )
            signal = self.strategy.generate_signal(
                market_data,
                symbol,
                current_position=position,
                simulation_time=simulation_time,
                cutoff=cutoff,
            )
            if signal.action == SignalAction.HOLD:
                return TradingRunResult(
                    signal, None, None, "HOLD", signal.reason or "strategy returned HOLD"
                )
            if signal.action not in (SignalAction.BUY, SignalAction.SELL):
                return TradingRunResult(
                    signal, None, None, "FAILED", "unsupported signal action"
                )

            try:
                price = Decimal(str(signal.price))
            except (InvalidOperation, TypeError, ValueError):
                return TradingRunResult(
                    signal, None, None, "FAILED", "signal price must be greater than 0"
                )
            if price <= Decimal("0"):
                return TradingRunResult(
                    signal, None, None, "FAILED", "signal price must be greater than 0"
                )

            risk_result = self.risk_evaluator.evaluate_trade(
                account,
                signal.symbol,
                signal.action.value,
                quantity,
                price,
                positions,
            )
            if not risk_result.allowed:
                return TradingRunResult(
                    signal,
                    risk_result,
                    None,
                    "RISK_REJECTED",
                    "; ".join(risk_result.reasons),
                )

            trade_result = self.paper_trading_service.execute_trade(
                account_id=account_id,
                symbol=signal.symbol,
                side=signal.action.value,
                quantity=quantity,
                requested_price=price,
                signal_id=signal.signal_id,
            )
            if trade_result.execution is None or trade_result.order.status.value != "FILLED":
                return TradingRunResult(
                    signal, risk_result, trade_result, "FAILED",
                    trade_result.order.rejection_reason or "paper trade was not filled",
                )
            return TradingRunResult(
                signal, risk_result, trade_result, "EXECUTED", "paper trade executed"
            )
        except Exception as exc:
            return TradingRunResult(
                locals().get("signal"),
                locals().get("risk_result"),
                locals().get("trade_result"),
                "FAILED",
                "trading run failed: " + str(exc),
            )

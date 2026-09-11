"""In-memory backtest configuration, ledger, and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
from config.settings import settings

from data.symbols import normalize_symbol


class BacktestExecutionTiming(str, Enum):
    NEXT_BAR_OPEN = "NEXT_BAR_OPEN"


class BacktestOrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class BacktestConfig:
    symbol: Any
    initial_cash: Decimal
    quantity: Decimal = Decimal("1")
    commission_rate: Decimal = settings.commission_rate
    slippage: Decimal = Decimal("0")
    execution_timing: BacktestExecutionTiming = BacktestExecutionTiming.NEXT_BAR_OPEN
    start_date: Optional[object] = None
    end_date: Optional[object] = None
    finalized_only: bool = True
    symbols: tuple = ()

    def __post_init__(self) -> None:
        raw_symbols = self.symbol if isinstance(self.symbol, (list, tuple)) else [self.symbol]
        canonical_symbols = tuple(sorted({normalize_symbol(symbol) for symbol in raw_symbols}))
        if not canonical_symbols:
            raise ValueError("at least one symbol is required")
        object.__setattr__(self, "symbol", canonical_symbols[0])
        object.__setattr__(self, "symbols", canonical_symbols)
        object.__setattr__(self, "initial_cash", Decimal(self.initial_cash))
        object.__setattr__(self, "quantity", Decimal(self.quantity))
        object.__setattr__(self, "commission_rate", Decimal(self.commission_rate))
        object.__setattr__(self, "slippage", Decimal(self.slippage))
        object.__setattr__(
            self, "execution_timing",
            BacktestExecutionTiming(self.execution_timing),
        )
        if self.initial_cash <= 0 or self.quantity <= 0:
            raise ValueError("initial_cash and quantity must be greater than 0")
        if self.commission_rate < 0 or self.slippage < 0:
            raise ValueError("commission_rate and slippage cannot be negative")


@dataclass
class BacktestPortfolio:
    cash: Decimal
    quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")
    positions: Dict[str, Decimal] = field(default_factory=dict)
    average_costs: Dict[str, Decimal] = field(default_factory=dict)

    def quantity_for(self, symbol: str) -> Decimal:
        return self.positions.get(symbol, Decimal("0"))

    def average_cost_for(self, symbol: str) -> Decimal:
        return self.average_costs.get(symbol, Decimal("0"))

    def apply_buy_for(self, symbol: str, quantity: Decimal, price: Decimal, fee: Decimal) -> None:
        old_quantity = self.quantity_for(symbol)
        total = old_quantity * self.average_cost_for(symbol) + quantity * price + fee
        self.positions[symbol] = old_quantity + quantity
        self.average_costs[symbol] = total / self.positions[symbol]
        self.cash -= quantity * price + fee
        self._sync_single(symbol)

    def apply_sell_for(self, symbol: str, quantity: Decimal, price: Decimal, fee: Decimal) -> Decimal:
        old_quantity = self.quantity_for(symbol)
        if quantity > old_quantity:
            raise ValueError("insufficient backtest position")
        pnl = (price - self.average_cost_for(symbol)) * quantity - fee
        remaining = old_quantity - quantity
        if remaining:
            self.positions[symbol] = remaining
        else:
            self.positions.pop(symbol, None)
            self.average_costs.pop(symbol, None)
        self.cash += quantity * price - fee
        self._sync_single(symbol)
        return pnl

    def _sync_single(self, symbol: str) -> None:
        if len(self.positions) == 1 and symbol in self.positions:
            self.quantity = self.positions[symbol]
            self.average_cost = self.average_costs[symbol]
        elif not self.positions:
            self.quantity = Decimal("0")
            self.average_cost = Decimal("0")

    def total_market_value(self, marks: Dict[str, Decimal]) -> Decimal:
        return sum(
            (quantity * marks[symbol] for symbol, quantity in self.positions.items()
             if symbol in marks),
            Decimal("0"),
        )

    def apply_buy(self, quantity: Decimal, price: Decimal, fee: Decimal) -> None:
        total = self.quantity * self.average_cost + quantity * price + fee
        self.quantity += quantity
        self.average_cost = total / self.quantity
        self.cash -= quantity * price + fee

    def apply_sell(self, quantity: Decimal, price: Decimal, fee: Decimal) -> Decimal:
        if quantity > self.quantity:
            raise ValueError("insufficient backtest position")
        pnl = (price - self.average_cost) * quantity - fee
        self.quantity -= quantity
        self.cash += quantity * price - fee
        if self.quantity == 0:
            self.average_cost = Decimal("0")
        return pnl

    def equity(self, mark_price: Decimal) -> Decimal:
        return self.cash + self.quantity * mark_price


@dataclass(frozen=True)
class BacktestOrder:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    signal_time: datetime
    execution_time: datetime
    status: BacktestOrderStatus
    reason: str


@dataclass(frozen=True)
class BacktestExecution:
    execution_id: str
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    executed_at: datetime


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    close: Decimal
    cash: Decimal
    position_quantity: Decimal
    position_market_value: Decimal
    total_equity: Decimal

    @property
    def quantity(self) -> Decimal:
        return self.position_quantity

    @property
    def equity(self) -> Decimal:
        return self.total_equity


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    side: str
    quantity: Decimal
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[Decimal]
    profit_loss_ratio: Optional[Decimal]


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    symbol: str
    initial_cash: Decimal
    final_cash: Decimal
    final_equity: Decimal
    orders: List[BacktestOrder]
    executions: List[BacktestExecution]
    equity_curve: List[EquityPoint]
    closed_trades: List[ClosedTrade]
    metrics: BacktestMetrics
    rejected_signals: List[Dict[str, Any]]
    visible_timestamps: List[datetime]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    bar_count: int
    order_count: int
    execution_count: int
    cancelled_count: int
    positions: Dict[str, Decimal]

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict


ZERO = Decimal("0")


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    weight: Decimal


@dataclass(frozen=True)
class PortfolioSnapshot:
    account_id: int
    cash: Decimal
    market_value: Decimal
    portfolio_value: Decimal
    exposure: Decimal
    positions: Dict[str, PositionSnapshot]

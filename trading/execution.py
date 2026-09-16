from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[Decimal] = None


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: OrderStatus
    symbol: str
    side: OrderSide
    quantity: int
    filled_quantity: int = 0
    average_price: Optional[Decimal] = None
    message: str = ""


class ExecutionBroker(ABC):
    """统一交易执行接口。

    策略和上层交易逻辑只依赖这个接口，
    不直接依赖 Paper、QMT 或 PTrade。
    """

    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResult:
        """提交订单。"""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单。"""
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """查询订单状态。"""
        raise NotImplementedError

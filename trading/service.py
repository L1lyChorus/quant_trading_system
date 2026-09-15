"""Paper Trading business rules and atomic transaction orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from config.settings import settings
from database.models import Account, Execution, Order, OrderStatus, Position
from trading.repository import TradingRepository

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


class TradeValidationError(ValueError):
    """Raised for invalid trade input or a rejected paper order."""


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TradeResult:
    order: Order
    execution: Optional[Execution]
    realized_pnl: Decimal = ZERO


class PaperTradingService:
    """Execute user-priced paper trades atomically in a supplied session."""

    def __init__(self, session: Session, commission_rate: Decimal = settings.commission_rate):
        self.session = session
        self.repository = TradingRepository(session)
        self.commission_rate = Decimal(commission_rate)

    def create_default_account(self, initial_cash: Decimal) -> Account:
        amount = self._positive(initial_cash, "initial_cash")
        existing = self.repository.get_default_account()
        if existing is not None:
            return existing
        account = Account(
            name="default_paper_account",
            initial_cash=amount,
            current_cash=amount,
        )
        self.repository.add_account(account)
        self.session.commit()
        logger.info("Account created: %s", account.id)
        return account

    def execute_trade(
        self,
        account_id: int,
        symbol: str,
        side: str,
        quantity: Decimal,
        requested_price: Decimal,
        signal_id: Optional[str] = None,
    ) -> TradeResult:
        symbol = symbol.strip().upper()
        quantity = Decimal(quantity)
        price = Decimal(requested_price)
        order = Order(
            order_id=str(uuid4()),
            account_id=account_id,
            symbol=symbol,
            side=side.upper(),
            quantity=quantity,
            requested_price=price,
            signal_id=signal_id,
            status=OrderStatus.PENDING,
        )
        self.repository.add_order(order)
        self.session.flush()
        account = self.repository.get_account(account_id)
        reason = self._rejection_reason(account, symbol, side, quantity, price)
        if reason is not None:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = reason
            self.session.commit()
            logger.info("Trade rejected: %s", reason)
            return TradeResult(order=order, execution=None)

        try:
            commission = price * quantity * self.commission_rate
            position = self.repository.get_position(account_id, symbol)
            realized_pnl = ZERO
            if order.side == Side.BUY.value:
                total_cost = price * quantity + commission
                account.current_cash -= total_cost
                if position is None:
                    position = Position(
                        account_id=account_id,
                        symbol=symbol,
                        quantity=quantity,
                        average_cost=total_cost / quantity,
                    )
                    self.repository.add_position(position)
                else:
                    old_cost = position.average_cost * position.quantity
                    position.quantity += quantity
                    position.average_cost = (old_cost + total_cost) / position.quantity
            else:
                realized_pnl = (price - position.average_cost) * quantity - commission
                account.current_cash += price * quantity - commission
                position.quantity -= quantity
                if position.quantity == ZERO:
                    self.repository.delete_position(position)

            execution = Execution(
                execution_id=str(uuid4()),
                order_id=order.id,
                symbol=symbol,
                side=order.side,
                price=price,
                quantity=quantity,
                commission=commission,
                executed_at=datetime.now(timezone.utc),
            )
            self.repository.add_execution(execution)
            self.session.flush()
            order.status = OrderStatus.FILLED
            order.commission = commission
            self.session.commit()
            logger.info("Trade filled: %s", order.order_id)
            return TradeResult(order, execution, realized_pnl)
        except Exception:
            self.session.rollback()
            logger.exception("Trade transaction failed")
            raise

    def _rejection_reason(
        self,
        account: Optional[Account],
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> Optional[str]:
        if account is None:
            return "account does not exist"
        if not symbol:
            return "symbol is required"
        if side.upper() not in (Side.BUY.value, Side.SELL.value):
            return "side must be BUY or SELL"
        if quantity <= ZERO:
            return "quantity must be greater than 0"
        if price <= ZERO:
            return "requested_price must be greater than 0"
        commission = price * quantity * self.commission_rate
        if side.upper() == Side.BUY.value and account.current_cash < price * quantity + commission:
            return "insufficient cash"
        position = self.repository.get_position(account.id, symbol)
        if side.upper() == Side.SELL.value and (
            position is None or position.quantity < quantity
        ):
            return "insufficient position"
        return None

    @staticmethod
    def _positive(value: Decimal, name: str) -> Decimal:
        amount = Decimal(value)
        if amount <= ZERO:
            raise TradeValidationError(name + " must be greater than 0")
        return amount

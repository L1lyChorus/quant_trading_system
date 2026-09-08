"""Persistence operations for paper trading, separate from business rules."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Account, Execution, Order, Position
from data.symbols import normalize_symbol


class TradingRepository:
    """Small data-access boundary used by the paper trading service."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_account(self, account_id: int) -> Optional[Account]:
        return self.session.get(Account, account_id)

    def get_default_account(self) -> Optional[Account]:
        return self.session.scalar(
            select(Account).where(Account.name == "default_paper_account")
        )

    def add_account(self, account: Account) -> Account:
        self.session.add(account)
        return account

    def add_order(self, order: Order) -> Order:
        self.session.add(order)
        return order

    def add_execution(self, execution: Execution) -> Execution:
        self.session.add(execution)
        return execution

    def get_position(self, account_id: int, symbol: str) -> Optional[Position]:
        symbol = normalize_symbol(symbol)
        return self.session.scalar(
            select(Position).where(
                Position.account_id == account_id, Position.symbol == symbol
            )
        )

    def get_positions(self, account_id: int):
        return list(
            self.session.scalars(
                select(Position).where(Position.account_id == account_id)
            )
        )

    def add_position(self, position: Position) -> Position:
        self.session.add(position)
        return position

    def delete_position(self, position: Position) -> None:
        self.session.delete(position)

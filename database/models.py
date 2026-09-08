"""SQLAlchemy schema foundation for paper-trading records."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PythonEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all database models."""


class OrderStatus(str, PythonEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    initial_funds: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("0"), nullable=False
    )
    current_cash: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    orders: Mapped[list[Order]] = relationship(back_populates="account")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    signal_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False
    )
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("0"), nullable=False
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    account: Mapped[Account] = relationship(back_populates="orders")
    executions: Mapped[list[Execution]] = relationship(back_populates="order")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("0"), nullable=False
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    order: Mapped[Order] = relationship(back_populates="executions")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

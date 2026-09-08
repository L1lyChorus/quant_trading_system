"""Independent, read-only risk rule evaluation."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from config.settings import settings
from risk_management.models import RiskResult
from data.symbols import normalize_symbol

ZERO = Decimal("0")
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _position_values(current_positions: Any) -> Iterable[Tuple[str, Decimal]]:
    if current_positions is None:
        return []
    if isinstance(current_positions, Mapping):
        items = current_positions.items()
    else:
        items = (
            (
                _value(position, "symbol"),
                _value(position, "quantity"),
            )
            for position in current_positions
        )
    result = []
    for symbol, quantity in items:
        parsed_quantity = _decimal(quantity)
        if symbol is not None and parsed_quantity is not None:
            try:
                canonical = normalize_symbol(symbol)
            except ValueError:
                canonical = str(symbol).strip()
            result.append((canonical, parsed_quantity))
    return result


class RiskEvaluator:
    """Evaluate all configured trade rules without persistence or side effects."""

    def __init__(
        self,
        commission_rate: Decimal = settings.commission_rate,
        max_trade_amount: Decimal = settings.max_trade_amount,
        max_total_position_ratio: Decimal = settings.max_total_position_ratio,
        max_single_position_ratio: Decimal = settings.max_single_position_ratio,
    ) -> None:
        self.commission_rate = Decimal(commission_rate)
        self.max_trade_amount = Decimal(max_trade_amount)
        self.max_total_position_ratio = Decimal(max_total_position_ratio)
        self.max_single_position_ratio = Decimal(max_single_position_ratio)

    def evaluate_trade(
        self,
        account: Any,
        symbol: str,
        side: str,
        quantity: Any,
        price: Any,
        current_positions: Any,
    ) -> RiskResult:
        reasons: List[str] = []
        rules: List[Dict[str, Any]] = []
        try:
            normalized_symbol = normalize_symbol(symbol) if symbol is not None else ""
        except ValueError:
            normalized_symbol = str(symbol).strip()
        normalized_side = str(side).strip().upper() if side is not None else ""
        parsed_quantity = _decimal(quantity)
        parsed_price = _decimal(price)
        current_cash = _decimal(_value(account, "current_cash"))
        positions = list(_position_values(current_positions))

        def add_rule(name: str, allowed: bool, reason: str = "", **metadata: Any) -> None:
            entry = {"rule": name, "allowed": allowed, "reason": reason}
            if metadata:
                entry["metadata"] = metadata
            rules.append(entry)
            if not allowed and reason:
                reasons.append(reason)

        add_rule(
            "price_positive",
            parsed_price is not None and parsed_price > ZERO,
            "price must be greater than 0",
        )
        add_rule(
            "quantity_positive",
            parsed_quantity is not None and parsed_quantity > ZERO,
            "quantity must be greater than 0",
        )
        add_rule(
            "symbol_valid",
            bool(SYMBOL_PATTERN.match(normalized_symbol)),
            "symbol is invalid",
        )
        add_rule(
            "side_valid",
            normalized_side in ("BUY", "SELL"),
            "side must be BUY or SELL",
        )

        arithmetic_ready = (
            parsed_price is not None
            and parsed_price > ZERO
            and parsed_quantity is not None
            and parsed_quantity > ZERO
        )
        trade_amount = (
            parsed_price * parsed_quantity if arithmetic_ready else None
        )
        commission = (
            trade_amount * self.commission_rate if trade_amount is not None else None
        )
        add_rule(
            "max_trade_amount",
            trade_amount is not None and trade_amount <= self.max_trade_amount,
            "trade amount exceeds MAX_TRADE_AMOUNT",
            trade_amount=trade_amount,
            limit=self.max_trade_amount,
        )
        buy_cost = trade_amount + commission if trade_amount is not None else None
        add_rule(
            "buy_cash_sufficient",
            normalized_side != "BUY"
            or (
                current_cash is not None
                and buy_cost is not None
                and current_cash >= buy_cost
            ),
            "insufficient cash for buy including commission",
        )

        quantities: Dict[str, Decimal] = {}
        for position_symbol, position_quantity in positions:
            quantities[position_symbol] = quantities.get(position_symbol, ZERO) + position_quantity
        existing_quantity = quantities.get(normalized_symbol, ZERO)
        sell_position_ok = (
            normalized_side != "SELL"
            or (
                parsed_quantity is not None
                and parsed_quantity > ZERO
                and existing_quantity >= parsed_quantity
            )
        )
        add_rule(
            "sell_position_sufficient",
            sell_position_ok,
            "insufficient position for sell",
            available_quantity=existing_quantity,
        )

        metadata: Dict[str, Any] = {
            "valuation_method": "all positions valued at proposed trade price",
            "commission": commission,
            "trade_amount": trade_amount,
        }
        ratio_rules_apply = normalized_side == "BUY" and arithmetic_ready
        if ratio_rules_apply:
            post_quantities = dict(quantities)
            post_quantities[normalized_symbol] = existing_quantity + parsed_quantity
            existing_market_value = sum(
                quantity * parsed_price
                for position_symbol, quantity in post_quantities.items()
                if position_symbol != normalized_symbol
            )
            target_market_value = post_quantities[normalized_symbol] * parsed_price
            post_cash = (
                current_cash - buy_cost if current_cash is not None and buy_cost is not None else None
            )
            total_equity = (
                post_cash + existing_market_value + target_market_value
                if post_cash is not None
                else None
            )
            total_ratio = (
                (existing_market_value + target_market_value) / total_equity
                if total_equity is not None and total_equity > ZERO
                else None
            )
            single_ratio = (
                target_market_value / total_equity
                if total_equity is not None and total_equity > ZERO
                else None
            )
            metadata.update(
                {
                    "post_cash": post_cash,
                    "total_equity": total_equity,
                    "post_total_position_value": existing_market_value + target_market_value,
                    "post_symbol_position_value": target_market_value,
                    "total_position_ratio": total_ratio,
                    "single_position_ratio": single_ratio,
                }
            )
            add_rule(
                "max_total_position_ratio",
                total_ratio is not None and total_ratio <= self.max_total_position_ratio,
                "post-trade total position ratio exceeds limit",
                ratio=total_ratio,
                limit=self.max_total_position_ratio,
            )
            add_rule(
                "max_single_position_ratio",
                single_ratio is not None and single_ratio <= self.max_single_position_ratio,
                "post-trade single position ratio exceeds limit",
                ratio=single_ratio,
                limit=self.max_single_position_ratio,
            )
        else:
            metadata["ratio_rules_skipped"] = normalized_side != "BUY"
            add_rule(
                "max_total_position_ratio",
                True,
                "BUY-only rule skipped for SELL or invalid arithmetic",
            )
            add_rule(
                "max_single_position_ratio",
                True,
                "BUY-only rule skipped for SELL or invalid arithmetic",
            )

        return RiskResult(
            allowed=all(rule["allowed"] for rule in rules),
            reasons=reasons,
            rule_results=rules,
            metadata=metadata,
        )


def evaluate_trade(
    account: Any,
    symbol: str,
    side: str,
    quantity: Any,
    price: Any,
    current_positions: Any,
) -> RiskResult:
    """Convenience function using the configured risk limits."""
    return RiskEvaluator().evaluate_trade(
        account, symbol, side, quantity, price, current_positions
    )

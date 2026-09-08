"""Independent risk-management rule tests."""

from decimal import Decimal

from sqlalchemy import func, select

from database.connection import initialize_database
from database.models import Account, Execution, Order, Position
from risk_management import RiskEvaluator, evaluate_trade


def account(cash="1000"):
    return {"current_cash": Decimal(cash)}


def evaluate(**kwargs):
    defaults = dict(
        account=account(),
        symbol="AAPL",
        side="BUY",
        quantity=Decimal("1"),
        price=Decimal("100"),
        current_positions={},
    )
    defaults.update(kwargs)
    return RiskEvaluator(
        max_trade_amount=Decimal("1000"),
        max_total_position_ratio=Decimal("0.80"),
        max_single_position_ratio=Decimal("0.50"),
    ).evaluate_trade(**defaults)


def test_normal_trade_is_allowed():
    result = evaluate()
    assert result.allowed is True


def test_invalid_price_and_quantity_are_rejected():
    result = evaluate(price=0, quantity=0)
    assert result.allowed is False
    assert len(result.reasons) >= 2


def test_invalid_symbol_and_side_are_rejected():
    result = evaluate(symbol="bad symbol", side="HOLD")
    assert result.allowed is False
    assert "symbol is invalid" in result.reasons
    assert "side must be BUY or SELL" in result.reasons


def test_max_trade_amount_is_enforced():
    result = evaluate(quantity=Decimal("11"), price=Decimal("100"))
    assert "trade amount exceeds MAX_TRADE_AMOUNT" in result.reasons


def test_buy_cash_includes_commission():
    result = evaluate(account=account("100.05"), quantity=1, price=100)
    assert "insufficient cash for buy including commission" in result.reasons


def test_sell_position_is_required():
    result = evaluate(side="SELL", quantity=2, current_positions={"AAPL": 1})
    assert "insufficient position for sell" in result.reasons


def test_total_position_ratio_is_enforced():
    result = evaluate(
        account=account("1000"),
        quantity=1,
        price=100,
        current_positions={"MSFT": 800},
    )
    assert "post-trade total position ratio exceeds limit" in result.reasons


def test_single_position_ratio_is_enforced():
    result = evaluate(account=account("1000"), quantity=6, price=100)
    assert "post-trade single position ratio exceeds limit" in result.reasons


def test_sell_skips_buy_only_position_ratio_rules():
    result = evaluate(
        account=account("1000"),
        side="SELL",
        quantity=1,
        price=100,
        current_positions={"AAPL": 1},
    )
    assert result.allowed is True
    assert result.rule_results[-1]["allowed"] is True


def test_all_failed_rules_are_retained():
    result = evaluate(
        account=account("0"),
        symbol="bad symbol",
        side="HOLD",
        quantity=0,
        price=0,
    )
    assert result.allowed is False
    assert len(result.reasons) >= 5
    assert len(result.rule_results) >= 8


def test_result_structure_and_metadata():
    result = evaluate()
    assert isinstance(result.allowed, bool)
    assert isinstance(result.reasons, list)
    assert isinstance(result.rule_results, list)
    assert result.metadata["valuation_method"]
    assert "commission" in result.metadata


def test_position_mapping_and_position_objects_are_supported():
    position = type("PositionInput", (), {"symbol": "AAPL", "quantity": Decimal("2")})()
    assert evaluate(current_positions=[position]).allowed is True


def test_total_equity_uses_post_trade_target_once():
    result = evaluate(
        account=account("1000"),
        quantity=1,
        price=100,
        current_positions={"AAPL": 2, "MSFT": 1},
    )
    assert result.metadata["post_symbol_position_value"] == Decimal("300")
    assert result.metadata["post_total_position_value"] == Decimal("400")


def test_risk_evaluation_does_not_modify_database():
    database = initialize_database("sqlite:///:memory:")
    with database.session() as session:
        before = {
            "accounts": session.scalar(select(func.count(Account.id))),
            "orders": session.scalar(select(func.count(Order.id))),
            "executions": session.scalar(select(func.count(Execution.id))),
            "positions": session.scalar(select(func.count(Position.id))),
        }
        evaluate()
        after = {
            "accounts": session.scalar(select(func.count(Account.id))),
            "orders": session.scalar(select(func.count(Order.id))),
            "executions": session.scalar(select(func.count(Execution.id))),
            "positions": session.scalar(select(func.count(Position.id))),
        }
        assert after == before


def test_convenience_evaluate_trade_uses_configured_interface():
    result = evaluate_trade(account(), "AAPL", "BUY", 1, 100, {})
    assert result.allowed is True


def test_risk_evaluation_does_not_call_paper_trading(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("PaperTradingService must not be called")

    monkeypatch.setattr(
        "trading.service.PaperTradingService.execute_trade", fail_if_called
    )
    assert evaluate().allowed is True


def test_sell_does_not_apply_ratio_rejection_even_with_large_position():
    result = evaluate(
        side="SELL",
        quantity=1,
        price=100,
        current_positions={"AAPL": 100},
    )
    assert result.allowed is True

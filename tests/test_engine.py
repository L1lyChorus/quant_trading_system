"""TradingEngine orchestration and safety tests."""

from decimal import Decimal

import pandas as pd
import pytest

from database.connection import initialize_database
from database.models import Account, Execution, Order, Position
from risk_management.models import RiskResult
from strategies.signals import Signal, SignalAction
from trading.engine import TradingEngine
from trading.service import PaperTradingService, TradeResult


def frame():
    return pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "datetime": pd.to_datetime(["2020-01-01"], utc=True),
            "open": [100],
            "high": [100],
            "low": [100],
            "close": [100],
            "volume": [10],
        }
    )


def signal(action=SignalAction.BUY, price=100):
    return Signal(
        "signal-1", "AAPL", action, pd.Timestamp("2020-01-01", tz="UTC").to_pydatetime(),
        price, "test", "test signal", {},
    )


class StubStrategy:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_signal(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class StubRisk:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def evaluate_trade(self, *args):
        self.calls.append(args)
        return self.result


class StubService:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def execute_trade(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def db_with_account():
    db = initialize_database("sqlite:///:memory:")
    context = db.session()
    session = context.__enter__()
    account = Account(name="default_paper_account", initial_cash=1000, current_cash=1000)
    session.add(account)
    session.commit()
    return db, context, session, account


def allowed_risk():
    return RiskResult(True, [], [{"rule": "all", "allowed": True}], {})


def test_hold_does_not_call_risk_or_service_or_write_database():
    db, context, session, account = db_with_account()
    risk = StubRisk(allowed_risk())
    service = StubService()
    strategy = StubStrategy(signal(SignalAction.HOLD))
    result = TradingEngine(session, strategy, risk, service).run_once(
        frame(), account.id, "AAPL", 1
    )
    assert result.status == "HOLD"
    assert risk.calls == []
    assert service.calls == []
    assert session.query(Order).count() == 0
    context.__exit__(None, None, None)


def test_buy_calls_strategy_risk_and_service_with_same_signal_price():
    db, context, session, account = db_with_account()
    risk = StubRisk(allowed_risk())
    service = StubService()
    result = TradingEngine(
        session, StubStrategy(signal()), risk, service
    ).run_once(frame(), account.id, "AAPL", 2)
    assert result.status == "FAILED"  # stub has no filled trade result
    assert risk.calls[0][4] == Decimal("100")
    assert service.calls[0]["requested_price"] == Decimal("100")
    context.__exit__(None, None, None)


def test_risk_rejection_does_not_call_service_or_write_order():
    db, context, session, account = db_with_account()
    risk = StubRisk(RiskResult(False, ["limit exceeded"], [], {}))
    service = StubService()
    result = TradingEngine(
        session, StubStrategy(signal()), risk, service
    ).run_once(frame(), account.id, "AAPL", 1)
    assert result.status == "RISK_REJECTED"
    assert service.calls == []
    assert session.query(Order).count() == 0
    context.__exit__(None, None, None)


def test_invalid_signal_price_fails_before_risk_or_service():
    db, context, session, account = db_with_account()
    risk = StubRisk(allowed_risk())
    service = StubService()
    result = TradingEngine(
        session, StubStrategy(signal(price=0)), risk, service
    ).run_once(frame(), account.id, "AAPL", 1)
    assert result.status == "FAILED"
    assert risk.calls == []
    assert service.calls == []
    context.__exit__(None, None, None)


def test_strategy_exception_returns_failed():
    db, context, session, account = db_with_account()
    class Failing:
        def generate_signal(self, *args, **kwargs):
            raise RuntimeError("strategy boom")
    result = TradingEngine(session, Failing()).run_once(frame(), account.id, "AAPL", 1)
    assert result.status == "FAILED"
    assert "strategy boom" in result.message
    context.__exit__(None, None, None)


def test_real_paper_buy_and_sell_integration():
    db, context, session, account = db_with_account()
    service = PaperTradingService(session)
    buy = TradingEngine(session, StubStrategy(signal()), paper_trading_service=service).run_once(
        frame(), account.id, "AAPL", 2
    )
    assert buy.status == "EXECUTED"
    sell_signal = signal(SignalAction.SELL, 110)
    sell = TradingEngine(
        session, StubStrategy(sell_signal), paper_trading_service=service
    ).run_once(frame(), account.id, "AAPL", 1)
    assert sell.status == "EXECUTED"
    assert sell.trade_result.execution.price == Decimal("110")
    context.__exit__(None, None, None)


@pytest.mark.parametrize("action", [SignalAction.BUY, SignalAction.SELL])
def test_result_fields_present_for_action(action):
    db, context, session, account = db_with_account()
    result = TradingEngine(
        session, StubStrategy(signal(action)), StubRisk(RiskResult(False, ["no"], [], {})),
        StubService()
    ).run_once(frame(), account.id, "AAPL", 1)
    assert result.signal is not None
    assert result.risk_result is not None
    assert result.trade_result is None
    assert result.status in ("RISK_REJECTED", "FAILED")
    assert result.message
    context.__exit__(None, None, None)

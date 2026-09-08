"""Offline tests for the single-symbol backtest MVP."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from backtesting import (
    BacktestConfig,
    BacktestEngine,
    BacktestExecutionTiming,
    BacktestOrderStatus,
)
from database.connection import initialize_database
from database.models import Account, MarketBar
from risk_management.models import RiskResult
from strategies.signals import Signal, SignalAction


def bars():
    values = [
        ("2024-01-01", 10, 10, "FINAL"),
        ("2024-01-02", 20, 21, "FINAL"),
        ("2024-01-03", 30, 31, "INTRADAY"),
        ("2024-01-04", 40, 40, "FINAL"),
    ]
    return [
        SimpleNamespace(
            symbol="600000.SH", datetime=pd.Timestamp(day, tz="UTC").to_pydatetime(),
            open=open_, high=open_, low=open_, close=close, volume=100,
            bar_status=status,
        )
        for day, open_, close, status in values
    ]


class FakeMarketData:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_historical_bars(self, symbol, start_date=None, end_date=None, finalized_only=True):
        self.calls.append((symbol, start_date, end_date, finalized_only))
        return self.rows


class BuyOnFirstVisibleBar:
    def __init__(self):
        self.frames = []

    def generate_signal(self, market_data, symbol, **kwargs):
        self.frames.append(market_data.copy())
        action = SignalAction.BUY if len(self.frames) == 1 else SignalAction.HOLD
        return Signal(
            "sig-" + str(len(self.frames)), symbol, action,
            market_data.iloc[-1]["datetime"].to_pydatetime(), 999,
            "test", "buy first" if action == SignalAction.BUY else "hold", {},
        )


class RejectRisk:
    def evaluate_trade(self, *args):
        return RiskResult(False, ["blocked"], [], {})


class BuyThenSell:
    def __init__(self):
        self.calls = 0

    def generate_signal(self, market_data, symbol, **kwargs):
        self.calls += 1
        action = SignalAction.BUY if self.calls == 1 else SignalAction.SELL
        return Signal(
            "trade-" + str(self.calls), symbol, action,
            market_data.iloc[-1]["datetime"].to_pydatetime(), 1,
            "test", action.value, {},
        )


class CaptureRisk:
    def __init__(self):
        self.calls = []

    def evaluate_trade(self, *args):
        self.calls.append(args)
        return RiskResult(True, [], [], {})


def run(strategy=None, risk=None, **kwargs):
    data = FakeMarketData(bars())
    engine = BacktestEngine(data, strategy or BuyOnFirstVisibleBar(), risk)
    return engine.run(BacktestConfig("600000", Decimal("1000"), **kwargs)), data


def test_config_canonicalizes_symbol_and_service_filters_final_bars_at_boundary():
    result, data = run()
    assert result.symbol == "600000.SH"
    assert data.calls == [("600000.SH", None, None, True)]
    assert [point.timestamp.date().isoformat() for point in result.equity_curve] == [
        "2024-01-01", "2024-01-02", "2024-01-04"
    ]


def test_signal_sees_only_current_and_prior_bars_and_fill_is_next_open():
    strategy = BuyOnFirstVisibleBar()
    result, _ = run(strategy)
    assert [len(frame) for frame in strategy.frames] == [1, 2, 3]
    assert result.executions[0].executed_at.date().isoformat() == "2024-01-02"
    assert result.executions[0].price == Decimal("20")


def test_signal_close_is_not_used_as_fill_price_and_future_data_is_not_visible():
    strategy = BuyOnFirstVisibleBar()
    result, _ = run(strategy)
    assert result.executions[0].price != Decimal("999")
    assert all(
        frame["datetime"].max().date().isoformat() <= timestamp.date().isoformat()
        for frame, timestamp in zip(strategy.frames, result.visible_timestamps[1:])
    )


def test_commission_and_slippage_are_applied_in_memory():
    result, _ = run(commission_rate=Decimal("0.1"), slippage=Decimal("1"))
    assert result.executions[0].price == Decimal("40")
    assert result.executions[0].commission == Decimal("4.0")
    assert result.final_cash == Decimal("956.0")


def test_hold_creates_no_order_and_risk_rejection_creates_no_execution():
    class Hold:
        def generate_signal(self, market_data, symbol, **kwargs):
            return Signal("hold", symbol, SignalAction.HOLD,
                          market_data.iloc[-1]["datetime"].to_pydatetime(),
                          10, "test", "hold", {})

    hold_result, _ = run(Hold())
    reject_result, _ = run(risk=RejectRisk())
    assert hold_result.orders == [] and hold_result.executions == []
    assert reject_result.orders == [] and reject_result.executions == []
    assert len(reject_result.rejected_signals) == 1


def test_empty_data_is_safe_and_reproducible():
    data = FakeMarketData([])
    config = BacktestConfig("600000.SH", Decimal("1000"))
    engine = BacktestEngine(data, BuyOnFirstVisibleBar())
    first = engine.run(config)
    second = engine.run(config)
    assert first.final_equity == second.final_equity == Decimal("1000")
    assert first.orders == second.orders == []


def test_backtest_does_not_touch_paper_sqlite():
    database = initialize_database("sqlite:///:memory:")
    with database.session() as session:
        session.add(Account(name="paper", initial_cash=1000, current_cash=1000))
        session.add(MarketBar(
            symbol="600000", datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=10, high=10, low=10, close=10, volume=1,
            source="TEST", fetched_at=datetime.now(timezone.utc), bar_status="FINAL",
        ))
        session.commit()
        before = (session.query(Account).count(), session.query(MarketBar).count())
    run()
    with database.session() as session:
        assert (session.query(Account).count(), session.query(MarketBar).count()) == before


def test_sell_uses_in_memory_position_and_records_both_legs():
    result, _ = run(BuyThenSell(), commission_rate=Decimal("0"))
    assert [order.side for order in result.orders] == ["BUY", "SELL", "SELL"]
    assert result.orders[-1].status is BacktestOrderStatus.CANCELLED
    assert [execution.executed_at.date().isoformat() for execution in result.executions] == [
        "2024-01-02", "2024-01-04"
    ]
    assert result.final_cash == Decimal("1020")


def test_risk_receives_backtest_cash_and_position_snapshot():
    risk = CaptureRisk()
    run(risk=risk)
    assert risk.calls[0][0]["current_cash"] == Decimal("1000")
    assert risk.calls[0][5] == {"600000.SH": Decimal("0")}


def test_result_contains_equity_curve_and_structured_ledger_fields():
    result, _ = run()
    assert len(result.equity_curve) == 3
    assert result.equity_curve[0].timestamp < result.equity_curve[-1].timestamp
    assert result.orders[0].order_id == result.executions[0].order_id
    assert result.orders[0].status == "FILLED"


def test_execution_timing_and_result_audit_metadata_are_configured():
    config = BacktestConfig("600000", Decimal("1000"))
    result, _ = run()
    assert config.execution_timing is BacktestExecutionTiming.NEXT_BAR_OPEN
    assert result.config == config
    assert result.bar_count == 3
    assert result.start_time == result.equity_curve[0].timestamp
    assert result.end_time == result.equity_curve[-1].timestamp
    assert result.order_count == len(result.orders)
    assert result.execution_count == len(result.executions)
    assert result.cancelled_count == 0


def test_zero_slippage_is_exact_next_open_and_runs_are_reproducible():
    first, _ = run(commission_rate=Decimal("0"), slippage=Decimal("0"))
    second, _ = run(commission_rate=Decimal("0"), slippage=Decimal("0"))
    assert first.executions[0].price == Decimal("20")
    assert first.orders == second.orders
    assert first.executions == second.executions


def test_config_controls_intraday_visibility_but_execution_still_uses_next_final_bar():
    result, data = run(finalized_only=False)
    assert data.calls[0][3] is False
    assert result.bar_count == 4
    assert all(execution.executed_at.date().isoformat() != "2024-01-03"
               for execution in result.executions)


def test_invalid_non_positive_execution_price_is_rejected():
    from backtesting.execution import BacktestExecutionAdapter
    from backtesting.models import BacktestPortfolio

    adapter = BacktestExecutionAdapter(
        BacktestConfig("600000", Decimal("1000")), BacktestPortfolio(Decimal("1000"))
    )
    try:
        adapter.execute(
            SignalAction.BUY,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 2, tzinfo=timezone.utc),
            Decimal("0"), Decimal("1"), "invalid", 1,
        )
    except ValueError as exc:
        assert "greater than 0" in str(exc)
    else:
        raise AssertionError("non-positive execution price was accepted")


def test_sell_slippage_uses_lower_next_open_price():
    result, _ = run(BuyThenSell(), commission_rate=Decimal("0"), slippage=Decimal("0.1"))
    assert result.executions[1].price == Decimal("36")


def test_equity_curve_has_complete_mark_to_market_fields_and_is_time_sorted():
    result, _ = run()
    point = result.equity_curve[1]
    assert point.timestamp < result.equity_curve[-1].timestamp
    assert point.cash == Decimal("979.980")
    assert point.position_quantity == Decimal("1")
    assert point.position_market_value == Decimal("21")
    assert point.total_equity == Decimal("1000.980")


def test_open_position_is_not_counted_as_closed_trade_but_is_marked_finally():
    result, _ = run()
    assert result.closed_trades == []
    assert result.metrics.total_trades == 0
    assert result.final_equity == Decimal("1019.980")
    assert result.metrics.winning_trades == 0
    assert result.metrics.losing_trades == 0
    assert result.metrics.win_rate is None


def test_closed_trade_metrics_use_only_realized_trades():
    result, _ = run(BuyThenSell(), commission_rate=Decimal("0"))
    metrics = result.metrics
    assert len(result.closed_trades) == 1
    assert result.closed_trades[0].pnl == Decimal("20")
    assert metrics.total_trades == 1
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 0
    assert metrics.win_rate == Decimal("1")
    assert metrics.profit_loss_ratio is None
    assert metrics.total_return == Decimal("0.02")


def test_annualized_return_uses_actual_curve_span_and_drawdown():
    result, _ = run(BuyThenSell(), commission_rate=Decimal("0"))
    assert result.metrics.annualized_return > Decimal("0")
    assert result.metrics.max_drawdown >= Decimal("0")


def test_metrics_are_safe_for_empty_curve():
    data = FakeMarketData([])
    result = BacktestEngine(data, BuyOnFirstVisibleBar()).run(
        BacktestConfig("600000", Decimal("1000"))
    )
    assert result.metrics.total_return == Decimal("0")
    assert result.metrics.annualized_return == Decimal("0")
    assert result.metrics.max_drawdown == Decimal("0")
    assert result.metrics.total_trades == 0

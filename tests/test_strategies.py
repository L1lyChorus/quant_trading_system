"""Read-only strategy signal tests."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from database.connection import initialize_database
from database.models import Account, Position
from strategies import MovingAverageCrossoverStrategy, SignalAction


def market(closes, symbol="AAPL"):
    dates = pd.date_range("2020-01-01", periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(closes),
            "datetime": dates,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100] * len(closes),
        }
    )


def test_strategy_parameters_are_validated():
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(0, 3)
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(3, 3)


def test_insufficient_data_returns_hold():
    signal = MovingAverageCrossoverStrategy(2, 4).generate_signal(
        market([1, 2, 3]), "aapl"
    )
    assert signal.action == SignalAction.HOLD
    assert "insufficient" in signal.reason


def test_no_cross_returns_hold():
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        market([5, 5, 5, 5, 5]), "AAPL"
    )
    assert signal.action == SignalAction.HOLD


def test_golden_cross_returns_buy():
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        market([5, 4, 3, 3, 7]), "AAPL"
    )
    assert signal.action == SignalAction.BUY
    assert "above" in signal.reason


def test_death_cross_returns_sell():
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        market([3, 4, 5, 5, 1]), "AAPL"
    )
    assert signal.action == SignalAction.SELL
    assert "below" in signal.reason


def test_continuous_rise_does_not_repeat_buy():
    strategy = MovingAverageCrossoverStrategy(2, 3)
    data = market([5, 4, 3, 3, 7, 8])
    assert strategy.generate_signal(data.iloc[:-1], "AAPL").action == SignalAction.BUY
    assert strategy.generate_signal(data, "AAPL").action == SignalAction.HOLD


def test_continuous_fall_does_not_repeat_sell():
    strategy = MovingAverageCrossoverStrategy(2, 3)
    data = market([3, 4, 5, 5, 1, 0.5])
    assert strategy.generate_signal(data.iloc[:-1], "AAPL").action == SignalAction.SELL
    assert strategy.generate_signal(data, "AAPL").action == SignalAction.HOLD


def test_signal_shape_and_metadata():
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        market([5, 4, 3, 6, 7]), "aapl"
    )
    assert signal.symbol == "AAPL"
    assert signal.price == 7.0
    assert signal.strategy_name == "moving_average_crossover"
    assert signal.signal_id
    assert set(signal.metadata) == {
        "short_ma", "long_ma", "previous_short_ma", "previous_long_ma",
        "short_window", "long_window",
    }


def test_cutoff_excludes_future_rows():
    data = market([5, 4, 3, 3, 7])
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        data, "AAPL", cutoff="2020-01-04T23:59:59Z"
    )
    assert signal.timestamp == datetime(2020, 1, 4, tzinfo=timezone.utc)
    assert signal.action == SignalAction.HOLD


def test_simulation_time_alias_excludes_future_rows():
    data = market([5, 4, 3, 6, 7])
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        data, "AAPL", simulation_time="2020-01-04T23:59:59Z"
    )
    assert signal.timestamp == datetime(2020, 1, 4, tzinfo=timezone.utc)


def test_strategy_does_not_modify_database():
    database = initialize_database("sqlite:///:memory:")
    with database.session() as session:
        before = set(session.query(Account).all())
        MovingAverageCrossoverStrategy(2, 3).generate_signal(
            market([5, 4, 3, 6, 7]), "AAPL"
        )
        assert set(session.query(Account).all()) == before
        assert session.query(Position).count() == 0


def test_strategy_does_not_call_paper_trading_service(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("PaperTradingService must not be called")

    monkeypatch.setattr(
        "trading.service.PaperTradingService.execute_trade", fail_if_called
    )
    signal = MovingAverageCrossoverStrategy(2, 3).generate_signal(
        market([5, 4, 3, 3, 7]), "AAPL"
    )
    assert signal.action == SignalAction.BUY

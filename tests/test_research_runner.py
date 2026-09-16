import pandas as pd

from research.experiment import ResearchExperiment
from research.ledger import ResearchLedger
from research.models import ResearchHypothesis
from research.runner import ResearchExperimentRunner


def make_hypothesis():
    return ResearchHypothesis(
        hypothesis_id="H001",
        title="放量上涨后的短期延续",
        economic_reason="成交量显著增加可能反映市场参与度和资金关注度上升。",
        variables=["return_1d", "volume_change", "future_return_5d"],
        expected_effect="放量上涨后未来5日收益率可能更高。",
        research_method="按成交量变化分组，比较不同组的未来收益。",
    )


def make_frame():
    return pd.DataFrame(
        {
            "open": [10, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "high": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            "low": [9, 9, 10, 11, 12, 13, 14, 15, 16, 17],
            "close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "volume": [100, 180, 200, 150, 250, 300, 320, 330, 340, 350],
        }
    )


def make_experiment():
    return ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="volume_change_gt_40pct",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )


def test_runner_executes_and_records_result():
    ledger = ResearchLedger()

    ledger.register_hypothesis(make_hypothesis())
    ledger.register_experiment(make_experiment())

    runner = ResearchExperimentRunner(ledger)

    result = runner.run(
        make_experiment(),
        make_frame(),
        lambda data: data["volume_change"] > 0.4,
    )

    assert result.experiment_id == "EXP001"
    assert result.hypothesis_id == "H001"
    assert result.sample_size == 2

    stored_results = ledger.get_results("H001")

    assert len(stored_results) == 1
    assert stored_results[0].experiment_id == "EXP001"

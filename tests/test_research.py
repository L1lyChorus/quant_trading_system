import pytest

from research.experiment import ResearchExperiment
from research.ledger import ResearchLedger
from research.models import ResearchHypothesis, ResearchResult


def make_hypothesis():
    return ResearchHypothesis(
        hypothesis_id="H001",
        title="放量上涨后的短期延续",
        economic_reason="成交量显著增加可能反映市场参与度和资金关注度上升。",
        variables=["return_1d", "volume_change", "future_return_5d"],
        expected_effect="放量上涨后未来5日收益率可能更高。",
        research_method="按成交量变化分组，比较不同组的未来收益。",
    )


def test_register_and_get_hypothesis():
    ledger = ResearchLedger()
    hypothesis = make_hypothesis()

    ledger.register_hypothesis(hypothesis)

    result = ledger.get_hypothesis("H001")

    assert result.title == "放量上涨后的短期延续"
    assert result.status == "PROPOSED"


def test_duplicate_hypothesis_is_rejected():
    ledger = ResearchLedger()
    hypothesis = make_hypothesis()

    ledger.register_hypothesis(hypothesis)

    try:
        ledger.register_hypothesis(hypothesis)
        assert False
    except ValueError as exc:
        assert "already exists" in str(exc)


def test_record_and_get_research_result():
    ledger = ResearchLedger()
    ledger.register_hypothesis(make_hypothesis())

    result = ResearchResult(
        hypothesis_id="H001",
        sample_size=1000,
        mean_return=0.018,
        median_return=0.012,
        win_rate=0.56,
        max_gain=0.15,
        max_drawdown=-0.08,
        sharpe_ratio=1.2,
        out_of_sample_return=0.011,
        transaction_cost_included=True,
    )

    ledger.record_result(result)

    results = ledger.get_results("H001")

    assert len(results) == 1
    assert results[0].sample_size == 1000
    assert results[0].win_rate == 0.56


def test_update_conclusion():
    ledger = ResearchLedger()
    ledger.register_hypothesis(make_hypothesis())

    ledger.update_conclusion(
        "H001",
        "样本内存在一定正向关系，但仍需进行样本外验证。",
        "TESTING",
    )

    hypothesis = ledger.get_hypothesis("H001")

    assert hypothesis.status == "TESTING"
    assert hypothesis.conclusion == "样本内存在一定正向关系，但仍需进行样本外验证。"


def test_unknown_hypothesis_is_rejected():
    ledger = ResearchLedger()

    try:
        ledger.get_hypothesis("UNKNOWN")
        assert False
    except KeyError as exc:
        assert "hypothesis not found" in str(exc)


def test_record_result_accepts_matching_experiment():
    ledger = ResearchLedger()

    hypothesis = ResearchHypothesis(
        hypothesis_id="H001",
        title="放量是否带来未来收益",
        economic_reason="成交量放大可能反映资金参与度提高",
        variables=["volume_change", "future_return_5d"],
        expected_effect="volume_change 越高，未来收益可能越高",
        research_method="条件统计",
    )

    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="volume_change_gt_40pct",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )

    ledger.register_hypothesis(hypothesis)
    ledger.register_experiment(experiment)

    result = ResearchResult(
        hypothesis_id="H001",
        experiment_id="EXP001",
        sample_size=10,
        mean_return=0.05,
        median_return=0.04,
        win_rate=0.6,
        max_gain=0.2,
        max_drawdown=-0.1,
    )

    ledger.record_result(result)

    assert ledger.get_results("H001") == [result]


def test_record_result_rejects_unknown_experiment():
    ledger = ResearchLedger()

    hypothesis = ResearchHypothesis(
        hypothesis_id="H001",
        title="放量是否带来未来收益",
        economic_reason="成交量放大可能反映资金参与度提高",
        variables=["volume_change"],
        expected_effect="未来收益增加",
        research_method="条件统计",
    )

    ledger.register_hypothesis(hypothesis)

    result = ResearchResult(
        hypothesis_id="H001",
        experiment_id="EXP999",
        sample_size=10,
        mean_return=0.05,
        median_return=0.04,
        win_rate=0.6,
        max_gain=0.2,
        max_drawdown=-0.1,
    )

    with pytest.raises(KeyError, match="experiment not found"):
        ledger.record_result(result)


def test_record_result_rejects_experiment_from_another_hypothesis():
    ledger = ResearchLedger()

    hypothesis_1 = ResearchHypothesis(
        hypothesis_id="H001",
        title="假设一",
        economic_reason="原因一",
        variables=["volume"],
        expected_effect="收益增加",
        research_method="条件统计",
    )

    hypothesis_2 = ResearchHypothesis(
        hypothesis_id="H002",
        title="假设二",
        economic_reason="原因二",
        variables=["volatility"],
        expected_effect="收益增加",
        research_method="条件统计",
    )

    experiment = ResearchExperiment(
        experiment_id="EXP002",
        hypothesis_id="H002",
        condition_name="high_volatility",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )

    ledger.register_hypothesis(hypothesis_1)
    ledger.register_hypothesis(hypothesis_2)
    ledger.register_experiment(experiment)

    result = ResearchResult(
        hypothesis_id="H001",
        experiment_id="EXP002",
        sample_size=10,
        mean_return=0.05,
        median_return=0.04,
        win_rate=0.6,
        max_gain=0.2,
        max_drawdown=-0.1,
    )

    with pytest.raises(
        ValueError,
        match="experiment does not belong to hypothesis",
    ):
        ledger.record_result(result)

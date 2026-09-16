import pytest

from research.experiment import ResearchExperiment


def test_research_experiment_valid():
    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="volume_spike",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
        parameters={
            "volume_change": "0.4",
            "future_window": "5",
        },
    )

    experiment.validate()

    assert experiment.experiment_id == "EXP001"
    assert experiment.hypothesis_id == "H001"
    assert experiment.condition_name == "volume_spike"
    assert experiment.parameters["volume_change"] == "0.4"


def test_research_experiment_requires_experiment_id():
    experiment = ResearchExperiment(
        experiment_id="",
        hypothesis_id="H001",
        condition_name="volume_spike",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )

    with pytest.raises(ValueError, match="experiment_id"):
        experiment.validate()


def test_research_experiment_requires_hypothesis_id():
    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="",
        condition_name="volume_spike",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )

    with pytest.raises(ValueError, match="hypothesis_id"):
        experiment.validate()


def test_research_experiment_requires_condition_name():
    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
    )

    with pytest.raises(ValueError, match="condition_name"):
        experiment.validate()


def test_research_experiment_requires_parameters_dict():
    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="volume_spike",
        data_source="test_market_data",
        start_date="2020-01-01",
        end_date="2025-12-31",
        parameters=["invalid"],
    )

    with pytest.raises(ValueError, match="parameters"):
        experiment.validate()


def test_research_experiment_rejects_invalid_date_range():
    experiment = ResearchExperiment(
        experiment_id="EXP001",
        hypothesis_id="H001",
        condition_name="volume_spike",
        data_source="test_market_data",
        start_date="2025-01-01",
        end_date="2024-01-01",
    )

    with pytest.raises(
        ValueError,
        match="start_date must not be after end_date",
    ):
        experiment.validate()

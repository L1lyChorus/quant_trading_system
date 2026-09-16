from __future__ import annotations

from typing import Callable

import pandas as pd

from research.experiment import ResearchExperiment
from research.ledger import ResearchLedger
from research.models import ResearchResult
from research.pipeline import ResearchPipeline


class ResearchExperimentRunner:
    """执行一次完整研究实验，并将结果登记到 ResearchLedger。"""

    def __init__(
        self,
        ledger: ResearchLedger,
        pipeline: ResearchPipeline | None = None,
    ) -> None:
        self.ledger = ledger
        self.pipeline = pipeline or ResearchPipeline()

    def run(
        self,
        experiment: ResearchExperiment,
        frame: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        future_return_column: str = "future_return_5d",
    ) -> ResearchResult:
        """执行实验并将结果登记到研究台账。"""

        experiment.validate()

        registered_experiment = self.ledger.get_experiment(
            experiment.experiment_id
        )

        if registered_experiment.hypothesis_id != experiment.hypothesis_id:
            raise ValueError(
                "experiment does not belong to hypothesis"
            )

        self.ledger.update_experiment_status(
            experiment.experiment_id,
            "RUNNING",
        )

        analysis = self.pipeline.analyzer.analyze(
            self.pipeline.prepare_features(frame),
            condition,
            future_return_column=future_return_column,
        )

        result = ResearchResult(
            hypothesis_id=experiment.hypothesis_id,
            sample_size=analysis.sample_size,
            mean_return=analysis.mean_return,
            median_return=analysis.median_return,
            win_rate=analysis.win_rate,
            max_gain=analysis.max_gain,
            max_drawdown=analysis.max_drawdown,
            experiment_id=experiment.experiment_id,
        )

        self.ledger.record_result(result)

        self.ledger.update_experiment_status(
            experiment.experiment_id,
            "COMPLETED",
        )

        return result

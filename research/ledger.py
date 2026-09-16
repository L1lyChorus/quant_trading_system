from __future__ import annotations

from typing import Dict, List

from research.experiment import ResearchExperiment
from research.models import ResearchHypothesis, ResearchResult


class ResearchLedger:
    """量化研究假设、实验与结果的统一登记台账。"""

    def __init__(self) -> None:
        self._hypotheses: Dict[str, ResearchHypothesis] = {}
        self._experiments: Dict[str, ResearchExperiment] = {}
        self._results: Dict[str, List[ResearchResult]] = {}

    def register_hypothesis(self, hypothesis: ResearchHypothesis) -> None:
        hypothesis.validate()

        if hypothesis.hypothesis_id in self._hypotheses:
            raise ValueError(
                f"hypothesis already exists: {hypothesis.hypothesis_id}"
            )

        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        self._results[hypothesis.hypothesis_id] = []

    def get_hypothesis(self, hypothesis_id: str) -> ResearchHypothesis:
        try:
            return self._hypotheses[hypothesis_id]
        except KeyError:
            raise KeyError(f"hypothesis not found: {hypothesis_id}")

    def list_hypotheses(self) -> List[ResearchHypothesis]:
        return list(self._hypotheses.values())

    def register_experiment(
        self,
        experiment: ResearchExperiment,
    ) -> None:
        experiment.validate()

        if experiment.experiment_id in self._experiments:
            raise ValueError(
                f"experiment already exists: {experiment.experiment_id}"
            )

        if experiment.hypothesis_id not in self._hypotheses:
            raise KeyError(
                f"hypothesis not found: {experiment.hypothesis_id}"
            )

        self._experiments[experiment.experiment_id] = experiment

    def get_experiment(
        self,
        experiment_id: str,
    ) -> ResearchExperiment:
        try:
            return self._experiments[experiment_id]
        except KeyError:
            raise KeyError(
                f"experiment not found: {experiment_id}"
            )

    def list_experiments(
        self,
        hypothesis_id: str | None = None,
    ) -> List[ResearchExperiment]:
        experiments = list(self._experiments.values())

        if hypothesis_id is None:
            return experiments

        if hypothesis_id not in self._hypotheses:
            raise KeyError(
                f"hypothesis not found: {hypothesis_id}"
            )

        return [
            experiment
            for experiment in experiments
            if experiment.hypothesis_id == hypothesis_id
        ]

    def update_experiment_status(
        self,
        experiment_id: str,
        status: str,
    ) -> None:
        experiment = self.get_experiment(experiment_id)

        if not status.strip():
            raise ValueError("status is required")

        experiment.status = status

    def record_result(self, result: ResearchResult) -> None:
        result.validate()

        if result.hypothesis_id not in self._hypotheses:
            raise KeyError(
                f"hypothesis not found: {result.hypothesis_id}"
            )

        if result.experiment_id is not None:
            if result.experiment_id not in self._experiments:
                raise KeyError(
                    f"experiment not found: {result.experiment_id}"
                )

            experiment = self._experiments[result.experiment_id]

            if experiment.hypothesis_id != result.hypothesis_id:
                raise ValueError(
                    "experiment does not belong to hypothesis"
                )

        self._results[result.hypothesis_id].append(result)

    def get_results(self, hypothesis_id: str) -> List[ResearchResult]:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"hypothesis not found: {hypothesis_id}")

        return list(self._results[hypothesis_id])

    def update_conclusion(
        self,
        hypothesis_id: str,
        conclusion: str,
        status: str,
    ) -> None:
        hypothesis = self.get_hypothesis(hypothesis_id)

        if not conclusion.strip():
            raise ValueError("conclusion is required")

        if not status.strip():
            raise ValueError("status is required")

        hypothesis.conclusion = conclusion
        hypothesis.status = status

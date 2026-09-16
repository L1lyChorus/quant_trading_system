from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class ResearchHypothesis:
    """可验证的量化研究假设。"""

    hypothesis_id: str
    title: str
    economic_reason: str
    variables: List[str]
    expected_effect: str
    research_method: str
    status: str = "PROPOSED"
    conclusion: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def validate(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")

        if not self.title.strip():
            raise ValueError("title is required")

        if not self.economic_reason.strip():
            raise ValueError("economic_reason is required")

        if not self.variables:
            raise ValueError("variables must not be empty")

        if not self.expected_effect.strip():
            raise ValueError("expected_effect is required")

        if not self.research_method.strip():
            raise ValueError("research_method is required")


@dataclass
class ResearchResult:
    """一次研究实验的结果。"""

    hypothesis_id: str
    sample_size: int
    mean_return: float
    median_return: float
    win_rate: float
    max_gain: float
    max_drawdown: float
    experiment_id: str | None = None
    sharpe_ratio: float | None = None
    out_of_sample_return: float | None = None
    transaction_cost_included: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")

        if self.sample_size <= 0:
            raise ValueError("sample_size must be greater than 0")

        if not 0 <= self.win_rate <= 1:
            raise ValueError("win_rate must be between 0 and 1")

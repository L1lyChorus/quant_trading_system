from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict


@dataclass
class ResearchExperiment:
    """一次可复现的量化研究实验。"""

    experiment_id: str
    hypothesis_id: str
    condition_name: str
    data_source: str = ""
    start_date: str = ""
    end_date: str = ""
    parameters: Dict[str, str] = field(default_factory=dict)
    status: str = "CREATED"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def validate(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")

        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")

        if not self.condition_name.strip():
            raise ValueError("condition_name is required")

        if not self.data_source.strip():
            raise ValueError("data_source is required")

        if not self.start_date.strip():
            raise ValueError("start_date is required")

        if not self.end_date.strip():
            raise ValueError("end_date is required")

        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")

        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")

        if not self.status.strip():
            raise ValueError("status is required")

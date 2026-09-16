from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class ResearchAnalysis:
    """一次条件研究的统计结果。"""

    sample_size: int
    mean_return: float
    median_return: float
    win_rate: float
    max_gain: float
    max_drawdown: float


class ResearchAnalyzer:
    """对已经计算好的研究特征进行条件分析。"""

    def analyze(
        self,
        frame: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        future_return_column: str = "future_return_5d",
    ) -> ResearchAnalysis:
        if future_return_column not in frame.columns:
            raise ValueError(
                f"missing future return column: {future_return_column}"
            )

        mask = condition(frame)

        if not isinstance(mask, pd.Series):
            raise ValueError("condition must return a pandas Series")

        selected = frame.loc[
            mask.astype(bool),
            future_return_column,
        ].dropna()

        if selected.empty:
            raise ValueError("no valid samples matched the condition")

        cumulative = (1 + selected).cumprod()
        running_peak = cumulative.cummax()
        drawdown = cumulative / running_peak - 1

        return ResearchAnalysis(
            sample_size=len(selected),
            mean_return=float(selected.mean()),
            median_return=float(selected.median()),
            win_rate=float((selected > 0).mean()),
            max_gain=float(selected.max()),
            max_drawdown=float(drawdown.min()),
        )

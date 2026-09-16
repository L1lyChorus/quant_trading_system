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


@dataclass(frozen=True)
class ResearchComparison:
    """条件组与对照组的收益比较结果。"""

    condition: ResearchAnalysis
    control: ResearchAnalysis
    mean_return_difference: float
    win_rate_difference: float


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


    def compare(
        self,
        frame: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        future_return_column: str = "future_return_5d",
    ) -> ResearchComparison:
        """比较条件组与对照组的未来收益。"""

        if future_return_column not in frame.columns:
            raise ValueError(
                f"missing future return column: {future_return_column}"
            )

        mask = condition(frame)

        if not isinstance(mask, pd.Series):
            raise ValueError("condition must return a pandas Series")

        mask = mask.astype(bool)

        condition_frame = frame.loc[mask]
        control_frame = frame.loc[~mask]

        condition_result = self.analyze(
            condition_frame,
            lambda data: pd.Series(True, index=data.index),
            future_return_column=future_return_column,
        )

        control_result = self.analyze(
            control_frame,
            lambda data: pd.Series(True, index=data.index),
            future_return_column=future_return_column,
        )

        return ResearchComparison(
            condition=condition_result,
            control=control_result,
            mean_return_difference=(
                condition_result.mean_return
                - control_result.mean_return
            ),
            win_rate_difference=(
                condition_result.win_rate
                - control_result.win_rate
            ),
        )

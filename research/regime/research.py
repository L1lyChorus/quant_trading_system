from __future__ import annotations

import pandas as pd

from research.analyzer import ResearchAnalyzer, ResearchAnalysis


class RegimeResearchAnalyzer:
    """分析研究条件在不同市场 Regime 下的表现。"""

    def __init__(
        self,
        analyzer: ResearchAnalyzer | None = None,
    ) -> None:
        self.analyzer = analyzer or ResearchAnalyzer()

    def analyze(
        self,
        frame: pd.DataFrame,
        condition,
        future_return_column: str = "future_return_5d",
    ) -> pd.DataFrame:
        if "regime_label" not in frame.columns:
            raise ValueError("missing required column: regime_label")

        results = []

        for regime_label in frame["regime_label"].dropna().unique():
            regime_frame = frame[
                frame["regime_label"] == regime_label
            ]

            try:
                analysis = self.analyzer.analyze(
                    regime_frame,
                    condition,
                    future_return_column=future_return_column,
                )
            except ValueError:
                continue

            results.append(
                {
                    "regime_label": regime_label,
                    "sample_size": analysis.sample_size,
                    "mean_return": analysis.mean_return,
                    "median_return": analysis.median_return,
                    "win_rate": analysis.win_rate,
                    "max_gain": analysis.max_gain,
                    "max_drawdown": analysis.max_drawdown,
                }
            )

        if not results:
            raise ValueError(
                "no valid regime samples matched the condition"
            )

        return pd.DataFrame(results)


    def filter_regime(
        self,
        frame: pd.DataFrame,
        trend: str | None = None,
        volatility: str | None = None,
        liquidity: str | None = None,
    ) -> pd.DataFrame:
        """按 Regime 的单个或多个维度筛选研究样本。"""

        required = {
            "trend_state",
            "volatility_state",
            "liquidity_state",
        }

        missing = required - set(frame.columns)

        if missing:
            raise ValueError(
                f"missing required regime columns: {sorted(missing)}"
            )

        mask = pd.Series(True, index=frame.index)

        if trend is not None:
            mask &= frame["trend_state"] == trend

        if volatility is not None:
            mask &= frame["volatility_state"] == volatility

        if liquidity is not None:
            mask &= frame["liquidity_state"] == liquidity

        return frame.loc[mask].copy()

from __future__ import annotations

from typing import Callable

import pandas as pd

from research.analyzer import ResearchAnalysis, ResearchAnalyzer
from research.features.basic import add_basic_features
from research.features.candlestick import add_candlestick_features
from research.regime.detector import MarketRegimeDetector


class ResearchPipeline:
    """统一执行市场特征计算与条件研究。"""

    def __init__(
        self,
        analyzer: ResearchAnalyzer | None = None,
        regime_detector: MarketRegimeDetector | None = None,
    ) -> None:
        self.analyzer = analyzer or ResearchAnalyzer()
        self.regime_detector = regime_detector or MarketRegimeDetector()

    def prepare_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        """计算基础特征和 K 线结构特征。"""
        result = add_basic_features(frame)
        result = add_candlestick_features(result)
        result = self.regime_detector.detect(result)
        return result

    def analyze(
        self,
        frame: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        future_return_column: str = "future_return_5d",
    ) -> ResearchAnalysis:
        """计算特征后执行条件研究。"""
        featured = self.prepare_features(frame)

        return self.analyzer.analyze(
            featured,
            condition,
            future_return_column=future_return_column,
        )

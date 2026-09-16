from __future__ import annotations

import pandas as pd


class RegimeAnalyzer:
    """统计历史数据中不同市场状态的出现情况。"""

    def analyze(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "regime_label" not in frame.columns:
            raise ValueError("missing required column: regime_label")

        counts = frame["regime_label"].value_counts(dropna=False)

        result = counts.rename("sample_size").to_frame()

        result["frequency"] = (
            result["sample_size"] / len(frame)
        )

        return result.reset_index(names="regime_label")

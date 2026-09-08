"""Extensible read-only strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from strategies.signals import Signal


class Strategy(ABC):
    """Generate a Signal from market data without side effects."""

    @abstractmethod
    def generate_signal(
        self,
        market_data: pd.DataFrame,
        symbol: str,
        current_position: Optional[Any] = None,
        simulation_time: Optional[datetime] = None,
        cutoff: Optional[datetime] = None,
    ) -> Signal:
        """Return a signal using only the supplied data and simulation cutoff."""

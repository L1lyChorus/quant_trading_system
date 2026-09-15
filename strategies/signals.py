"""Common, execution-free strategy signal data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    """A strategy judgment; it never represents an executed trade."""

    signal_id: str
    symbol: str
    action: SignalAction
    timestamp: datetime
    price: float
    strategy_name: str
    reason: str
    metadata: Dict[str, Any]

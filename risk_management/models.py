"""Risk evaluation result structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class RiskResult:
    """Complete, non-mutating result of evaluating a proposed trade."""

    allowed: bool
    reasons: List[str]
    rule_results: List[Dict[str, Any]]
    metadata: Dict[str, Any]

"""CSV market data reader, duplicate handling, and simulation cutoff filtering."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from data.validation import DataValidationError, validate_market_data


class DuplicatePolicy(str, Enum):
    RAISE = "raise"
    DROP = "drop"


def read_market_csv(
    path: Union[str, Path],
    cutoff: Optional[object] = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RAISE,
) -> pd.DataFrame:
    """Read, validate, sort, and optionally cutoff local OHLCV CSV data.

    Duplicate records are identified by ``symbol`` and ``datetime``. By
    default they raise an explicit error; ``DROP`` keeps the first record.
    ``cutoff`` is a simulation timestamp and does not compare against now.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataValidationError("CSV file does not exist: " + str(csv_path))
    try:
        raw = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError) as exc:
        raise DataValidationError("could not read CSV: " + str(exc)) from exc

    normalized = validate_market_data(raw)
    duplicate_mask = normalized.duplicated(["symbol", "datetime"], keep=False)
    if duplicate_mask.any():
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_policy == DuplicatePolicy.DROP:
            normalized = normalized.drop_duplicates(
                ["symbol", "datetime"], keep="first"
            ).reset_index(drop=True)
        else:
            raise DataValidationError(
                "duplicate market records found for symbol/datetime: "
                + str(duplicate_count)
            )
    elif duplicate_policy not in (DuplicatePolicy.RAISE, DuplicatePolicy.DROP):
        raise DataValidationError(
            "duplicate_policy must be DuplicatePolicy.RAISE or DROP"
        )

    if cutoff is not None:
        cutoff_timestamp = pd.to_datetime(cutoff, errors="coerce", utc=True)
        if pd.isna(cutoff_timestamp):
            raise DataValidationError("cutoff must be a valid ISO 8601 datetime")
        normalized = normalized[
            normalized["datetime"] <= cutoff_timestamp
        ].reset_index(drop=True)

    return normalized

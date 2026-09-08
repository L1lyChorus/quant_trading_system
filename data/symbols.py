"""Canonical security identifiers used by market-data boundaries."""

from __future__ import annotations

import re


def normalize_symbol(symbol: str) -> str:
    """Return ``600000.SH``/``000001.SZ`` for A-shares."""
    value = str(symbol).strip().upper()
    match = re.fullmatch(r"([036]\d{5})(?:\.(SH|SZ))?", value)
    if not match:
        return value
    code, suffix = match.groups()
    expected = "SH" if code.startswith(("5", "6", "9")) else "SZ"
    if suffix and suffix != expected:
        raise ValueError("A-share market suffix does not match symbol")
    return code + "." + expected


def a_share_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not re.fullmatch(r"[036]\d{5}\.(SH|SZ)", normalized):
        raise ValueError("A-share symbol must be six digits")
    return normalized[:6]

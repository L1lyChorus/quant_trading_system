"""Canonical news DTOs and validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional


class NewsRegion(str, Enum):
    CHINA = "CHINA"
    GLOBAL = "GLOBAL"


class NewsCategory(str, Enum):
    MACRO = "MACRO"
    POLICY = "POLICY"
    MARKET = "MARKET"
    COMPANY = "COMPANY"
    CENTRAL_BANK = "CENTRAL_BANK"
    REGULATION = "REGULATION"
    OTHER = "OTHER"


class NewsValidationError(ValueError):
    """Raised for malformed or incomplete normalized news."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class NewsItemDTO:
    title: str
    summary: str
    source: str
    source_type: str
    url: str
    published_at: Optional[datetime]
    fetched_at: datetime
    region: NewsRegion
    category: NewsCategory
    language: str
    id: str = field(default="")

    def __post_init__(self) -> None:
        published = (
            self.published_at.astimezone(timezone.utc)
            if self.published_at is not None
            else None
        )
        fetched = self.fetched_at.astimezone(timezone.utc)
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "fetched_at", fetched)
        if not self.title.strip() or not self.source.strip() or not self.url.strip():
            raise NewsValidationError("title, source, and url are required")
        if not self.id:
            object.__setattr__(
                self,
                "id",
                hashlib.sha256(self.url.strip().encode("utf-8")).hexdigest(),
            )

"""Public RSS providers using stdlib networking and XML parsing."""

from __future__ import annotations

import html
import socket
import urllib.request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from news.models import NewsCategory, NewsItemDTO, NewsRegion, NewsValidationError, utc_now


class NewsProviderError(RuntimeError):
    """Base error for network or provider-format failures."""


class NewsNetworkError(NewsProviderError):
    """Raised when an RSS source cannot be reached."""


class NewsUnavailableError(NewsProviderError):
    """Raised when a source is reachable but unavailable (for example 404)."""


class NewsFormatError(NewsProviderError):
    """Raised when an RSS response is not parseable."""


class NewsProvider(ABC):
    name = "public_rss"
    source_type = "RSS"
    region = NewsRegion.GLOBAL
    language = "en"
    category = NewsCategory.OTHER

    def __init__(self, url: str, timeout: int = 10) -> None:
        self.url = url
        self.timeout = timeout

    @abstractmethod
    def fetch(self) -> List[NewsItemDTO]:
        pass


class RSSProvider(NewsProvider):
    allow_missing_published = False

    def fetch(self) -> List[NewsItemDTO]:
        request = urllib.request.Request(
            self.url, headers={"User-Agent": "quant-trading-system/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as exc:
            if exc.code in (403, 404, 410):
                raise NewsUnavailableError(
                    "{} unavailable: HTTP {}".format(self.name, exc.code)
                ) from exc
            raise NewsNetworkError("{} HTTP error: {}".format(self.name, exc)) from exc
        except (OSError, socket.timeout) as exc:
            raise NewsNetworkError("{} network error: {}".format(self.name, exc)) from exc
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise NewsFormatError("{} returned invalid XML".format(self.name)) from exc

        items = []
        fetched = utc_now()
        for item in root.findall(".//item"):
            title = self._text(item, "title")
            url = self._text(item, "link")
            published_raw = self._text(item, "pubDate") or self._text(item, "pubTime")
            if not title or not url or (not published_raw and not self.allow_missing_published):
                raise NewsFormatError("{} item missing title/link/pubDate".format(self.name))
            published = None
            if published_raw:
                try:
                    try:
                        published = parsedate_to_datetime(published_raw)
                    except (TypeError, ValueError, OverflowError):
                        published = datetime.strptime(
                            published_raw, "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=timezone.utc)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise NewsFormatError("{} item has invalid pubDate".format(self.name)) from exc
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            items.append(
                NewsItemDTO(
                    title=html.unescape(title).strip(),
                    summary=html.unescape(self._text(item, "description")),
                    source=self.name,
                    source_type=self.source_type,
                    url=url.strip(),
                    published_at=published,
                    fetched_at=fetched,
                    region=self.region,
                    category=self.category,
                    language=self.language,
                )
            )
        return items

    @staticmethod
    def _text(parent: ET.Element, name: str) -> str:
        element = parent.find(name)
        return (element.text or "").strip() if element is not None else ""


class GovChinaRSSProvider(RSSProvider):
    name = "中国政府网"
    region = NewsRegion.CHINA
    language = "zh"
    category = NewsCategory.POLICY
    allow_missing_published = True

    def __init__(self, url: str = "https://www.gov.cn/rss/zhengce.xml", timeout: int = 10):
        super().__init__(url, timeout)


class ChinaDailyRSSProvider(RSSProvider):
    name = "China Daily"
    region = NewsRegion.CHINA
    language = "en"
    category = NewsCategory.MARKET
    allow_missing_published = True

    def __init__(
        self,
        url: str = "https://www.chinadaily.com.cn/rss/china_rss.xml",
        timeout: int = 10,
    ):
        super().__init__(url, timeout)


class ECBRSSProvider(RSSProvider):
    name = "European Central Bank"
    region = NewsRegion.GLOBAL
    language = "en"
    category = NewsCategory.CENTRAL_BANK

    def __init__(
        self,
        url: str = "https://www.ecb.europa.eu/rss/press.html",
        timeout: int = 10,
    ):
        super().__init__(url, timeout)


class FederalReserveRSSProvider(RSSProvider):
    name = "Federal Reserve"
    region = NewsRegion.GLOBAL
    language = "en"
    category = NewsCategory.CENTRAL_BANK

    def __init__(
        self,
        url: str = "https://www.federalreserve.gov/feeds/press_all.xml",
        timeout: int = 10,
    ):
        super().__init__(url, timeout)


class PBOCProvider(RSSProvider):
    name = "PBOC"
    region = NewsRegion.CHINA
    language = "zh"
    category = NewsCategory.CENTRAL_BANK

    def __init__(
        self,
        url: str = "https://www.pbc.gov.cn/goutongjiaoliu/113456/2986536/index.html",
        timeout: int = 10,
    ):
        super().__init__(url, timeout)


class NBSProvider(RSSProvider):
    region = NewsRegion.CHINA
    language = "zh"
    category = NewsCategory.MACRO

    def __init__(self, feed: str = "data", timeout: int = 10):
        urls = {
            "data": "https://www.stats.gov.cn/sj/zxfb/rss.xml",
            "interpretation": "https://www.stats.gov.cn/sj/sjjd/rss.xml",
        }
        if feed not in urls:
            raise ValueError("feed must be data or interpretation")
        self.feed = feed
        self.name = "NBS data" if feed == "data" else "NBS interpretation"
        super().__init__(urls[feed], timeout)

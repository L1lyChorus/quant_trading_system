"""Offline A-share provider parser and freshness tests."""

from datetime import datetime, timezone

import pytest

from data.a_share import MarketDataError, TencentAShareProvider
from data.health import FreshnessStatus


def test_tencent_quote_parser_and_old_status(monkeypatch):
    raw = (
        'v_sh600000="1~浦发银行~600000~9.23~9.43~9.43~867113~397712~469401~'
        '9.23~1408~9.22~6882~9.21~4263~9.20~8147~9.19~7995~9.24~1587~9.25~'
        '1315~9.26~3322~9.27~947~9.28~1261~~20200101100000~-0.20~-2.12~'
        '9.46~9.19~9.23/867113/806326225~867113~80633~0.26~6.00~~9.46~9.19~'
        '2.86~3074.13~3074.13~0.41~10.37~8.49~1.00";'
    ).encode("gbk")

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return raw

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    quote = TencentAShareProvider().fetch_quote("600000")
    assert quote.name == "浦发银行"
    assert quote.price == 9.23
    assert quote.freshness_status == FreshnessStatus.OUTDATED


def test_tencent_network_error(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("blocked")
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(MarketDataError, match="network"):
        TencentAShareProvider().fetch_quote("600000")


def test_invalid_symbol():
    with pytest.raises(MarketDataError):
        TencentAShareProvider().fetch_quote("AAPL")

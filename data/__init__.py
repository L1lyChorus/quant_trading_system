"""Local market data loading and validation."""

from importlib import import_module


_EXPORTS = {
    "DuplicatePolicy": ("data.csv_reader", "DuplicatePolicy"),
    "read_market_csv": ("data.csv_reader", "read_market_csv"),
    "REQUIRED_COLUMNS": ("data.validation", "REQUIRED_COLUMNS"),
    "DataValidationError": ("data.validation", "DataValidationError"),
    "validate_market_data": ("data.validation", "validate_market_data"),
    "AShareQuote": ("data.a_share", "AShareQuote"),
    "TencentAShareProvider": ("data.a_share", "TencentAShareProvider"),
    "FreshnessStatus": ("data.health", "FreshnessStatus"),
    "MarketHealthResult": ("data.health", "MarketHealthResult"),
    "MarketQuote": ("data.market", "MarketQuote"),
    "MarketDataProvider": ("data.market", "MarketDataProvider"),
    "TencentMarketDataProvider": ("data.market", "TencentMarketDataProvider"),
    "EastmoneyMarketDataProvider": ("data.market", "EastmoneyMarketDataProvider"),
    "PrimaryFallbackMarketProvider": ("data.market", "PrimaryFallbackMarketProvider"),
    "normalize_symbol": ("data.symbols", "normalize_symbol"),
    "a_share_code": ("data.symbols", "a_share_code"),
    "HistoricalDataError": ("data.historical", "HistoricalDataError"),
    "HistoricalFetchStatus": ("data.historical", "HistoricalFetchStatus"),
    "HistoricalFetchResult": ("data.historical", "HistoricalFetchResult"),
    "BarStatus": ("data.historical", "BarStatus"),
    "HistoricalDataProvider": ("data.historical", "HistoricalDataProvider"),
    "HistoricalDataService": ("data.historical", "HistoricalDataService"),
    "UserCSVHistoricalDataProvider": ("data.historical", "UserCSVHistoricalDataProvider"),
    "EastmoneyHistoricalDataProvider": ("data.historical", "EastmoneyHistoricalDataProvider"),
    "SinaHistoricalDataProvider": ("data.historical", "SinaHistoricalDataProvider"),
    "PrimaryFallbackHistoricalDataProvider": (
        "data.historical",
        "PrimaryFallbackHistoricalDataProvider",
    ),
    "MarketDataService": ("data.service", "MarketDataService"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'data' has no attribute {name!r}")

    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attribute_name)

    globals()[name] = value
    return value


__all__ = list(_EXPORTS)

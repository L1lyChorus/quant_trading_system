"""Local market data loading and validation."""

from data.a_share import AShareQuote, TencentAShareProvider
from data.market import (
    EastmoneyMarketDataProvider,
    MarketDataProvider,
    MarketQuote,
    PrimaryFallbackMarketProvider,
    TencentMarketDataProvider,
)
from data.health import FreshnessStatus, MarketHealthResult
from data.csv_reader import DuplicatePolicy, read_market_csv
from data.validation import REQUIRED_COLUMNS, DataValidationError, validate_market_data
from data.historical import (
    HistoricalDataError,
    HistoricalDataProvider,
    HistoricalDataService,
    UserCSVHistoricalDataProvider,
)

__all__ = [
    "DuplicatePolicy",
    "REQUIRED_COLUMNS",
    "DataValidationError",
    "AShareQuote",
    "TencentAShareProvider",
    "FreshnessStatus",
    "MarketHealthResult",
    "MarketQuote",
    "MarketDataProvider",
    "TencentMarketDataProvider",
    "EastmoneyMarketDataProvider",
    "PrimaryFallbackMarketProvider",
    "read_market_csv",
    "validate_market_data",
    "HistoricalDataError",
    "HistoricalDataProvider",
    "HistoricalDataService",
    "UserCSVHistoricalDataProvider",
]

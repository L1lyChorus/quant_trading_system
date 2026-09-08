# Quant Trading System

Step 1 establishes the project foundation for a paper-trading MVP. It provides
configuration, logging, SQLite schema initialization, and package boundaries for
future business logic and data access.

## Requirements

- Python 3.9.6+
- Dependencies in `requirements.txt`

## Setup

```bash
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

The default database is `quant_trading.db` and live trading is explicitly
disabled (`LIVE_TRADING_ENABLED=false`). No broker integration or real trading
logic is included in this step.

## Stage 2: local market data

The `data/` module reads local CSV OHLCV data into a normalized Pandas
DataFrame, validates required fields and values, sorts by timestamp, detects
duplicate `symbol`/`datetime` records, and supports a simulation cutoff
timestamp. Cutoffs are historical simulation inputs and are never compared
against the real current date.

Market data is intentionally not stored in SQLite yet. Keeping ingestion and
validation separate from the Step 1 trading schema avoids coupling this stage
to persistence before a market-data storage model is required.

Example:

```bash
python -c "from data import read_market_csv; print(read_market_csv('data/example_market_data.csv'))"
```

## Stage 3: Paper Trading

`trading.service.PaperTradingService` executes paper orders immediately at the
user-supplied price. It creates the order, execution, cash update, and position
update in one SQLAlchemy transaction. The configurable `COMMISSION_RATE`
defaults to `0.001`; buy commission is included in the position average cost,
and sell commission is deducted from realized P&L and cash.

The default paper account is persisted in SQLite. Initial cash is immutable
after account creation. When a position is fully sold, its row is deleted
instead of retained at zero so holdings queries only return open positions and
future analysis does not need to interpret zero-quantity rows.

The account schema uses `initial_cash` as the single initial-balance field.
The former duplicate `initial_funds` field was removed; this development
database uses SQLAlchemy `create_all`, so no migration is required.

This stage does not include a Streamlit application, strategy, indicator,
news, backtest, broker, or live-trading integration.

## Stage 4: strategy signals

`MovingAverageCrossoverStrategy` is read-only: it consumes validated OHLCV
data and returns a `Signal` without changing accounts, positions, or SQLite.
It uses only rows at or before the supplied `cutoff`/`simulation_time`.

## Stage 5: risk management

`risk_management` is an independent, read-only evaluator. It returns a
`RiskResult` containing every rule result, all rejection reasons, and valuation
metadata. It does not connect to strategies, call `PaperTradingService`, or
create database records. BUY-only portfolio-ratio rules use post-trade
positions and value all holdings at the proposed trade price; SELL skips those
ratio rules.

## Stage 7: public news

The independent `news` module normalizes public RSS items into `NewsItemDTO`
records and persists them in the `news_items` table. It includes adapters for
China Daily's public China RSS, European Central Bank public press RSS, Federal
Reserve public press-release RSS, and a China Government policy RSS adapter.
Refresh is on demand: it fetches, validates, deduplicates by URL and by
source/title, then commits new rows without deleting existing news. Each
provider reports `AVAILABLE`, `UNAVAILABLE`, or `ERROR`, with item counts and
source-specific errors; one provider failure does not stop another.

The Federal Reserve, ECB, and China Daily feeds were reachable during
validation. China Daily's feed does not provide a reliable publication field
for its items, so `published_at` remains null rather than being fabricated.
The configured China Government RSS endpoint was probed separately and
returned HTTP 404; its adapter reports `UNAVAILABLE`, and no successful
government-feed fetch is claimed.

This is not guaranteed real-time; availability and publisher delay determine
latency. News is informational only and is not investment advice. The module
does not generate trading signals, drive the dashboard, schedule jobs, or
execute trades.

## Stage 8: source freshness and A-share quotes

The `news` and `data` modules expose separate health checks with
`FRESH`/`STALE`/`OUTDATED`/`UNKNOWN`/`ERROR` statuses. Content timestamps are
used for `data_age`; fetch time is never treated as content time. Thresholds
are configured through the `*_FRESH_THRESHOLD_SECONDS` and
`*_STALE_THRESHOLD_SECONDS` settings.

The verified public Tencent quote endpoint
(`https://qt.gtimg.cn/q=sh600000`) requires no API key and returned a quote
during investigation, but its timestamp was the previous market session
(`2026-09-07 16:14:45+08:00` at the 2026-09-08 check). With the configured
24-hour outdated threshold it was measured as `STALE`, not real-time. China Daily was reachable but its sample content
was from 2017 with no reliable publication timestamp, so news freshness is
`UNKNOWN`. These results do not trigger trading or modify existing records.

The specified PBOC URL and both NBS RSS URLs are implemented as explicit
providers. A live probe on 2026-09-08 returned parseable RSS from PBOC (6
items), NBS data (500 items), and NBS interpretation (500 items); NBS uses
its `pubTime` field and PBOC uses its RSS publication field. Refresh can use
the configured `NEWS_REFRESH_INTERVAL_MINUTES` (default 15) and remains on
demand; provider failures are isolated and each provider has its own status
key.

The exact Tencent endpoint returned a quote for `600000` during live
validation (price `9.24`, vendor timestamp `2026-09-08T02:34:58Z`, fetched
`2026-09-08T02:35:02Z`, measured age about 4 seconds, status `FRESH`). The
market session is reported separately; no quote is called real-time outside
the fixed weekday trading windows. The exact Eastmoney endpoint returned HTTP
200 in an earlier probe and had no reliable timestamp (`UNKNOWN`), but a
later validation failed with `Remote end closed connection without response`;
this is reported as a provider error rather than fabricated data. The
minimal `market_calendar` uses Asia/Shanghai fixed weekday sessions and does
not include official holiday closures. Primary/fallback selection only calls
the fallback after a primary error and preserves the selected quote's own
freshness metadata.

## Stage 6: trading engine

`TradingEngine.run_once` coordinates one strategy signal, risk evaluation, and
paper execution. HOLD stops after the signal; risk rejection never creates an
order; allowed BUY/SELL uses the exact signal price for both risk and execution
and passes the signal ID to `PaperTradingService`. Optional valuation-price
inputs are reserved for future extensions; current risk valuation remains
configured by the risk module.

## Checks

```bash
pytest -q
python main.py
```

## Stage 9: A-share calendar and historical OHLCV

`market_calendar` separates date-level trading-day knowledge from intraday
session classification. It uses `Asia/Shanghai` and exposes `UNKNOWN`,
`CLOSED`, `PRE_OPEN`, `AUCTION`, `TRADING`, `MIDDAY_BREAK`, `AFTER_HOURS`,
`HOLIDAY`, and `WEEKEND`. A weekday absent from an explicitly loaded calendar
is `UNKNOWN`; it is never assumed to be open. The calendar can be loaded from
a user CSV with `date,is_open` columns.

`data.historical` provides the `HistoricalDataProvider` interface and a
`UserCSVHistoricalDataProvider`. CSV rows use the existing normalized
`symbol,datetime,open,high,low,close,volume` format. Ingestion validates
positive OHLC values, non-negative volume, timestamps, and symbols; deduplicates
`symbol`/`datetime`, sorts chronologically, and upserts into the independent
`market_bars` SQLite table. Each row stores `source` and UTC `fetched_at`, and
the unique key makes repeated or incremental updates safe.

Internally, A-share identifiers are canonicalized to `600000.SH`/`000001.SZ`
(legacy six-digit inputs remain accepted at the API boundary). Quote adapters
only produce quote objects; historical adapters produce OHLCV bars. Eastmoney
is the primary historical upstream and Sina is the independent fallback
upstream; their HTTP transport and upstream names are retained in fetch
results. A primary `EMPTY`, `ERROR`, or `UNAVAILABLE` result permits fallback,
while the selected result's actual source and the primary reason are preserved.

The historical service supports Eastmoney as the primary daily OHLCV provider
and Sina as the fallback, while `USER_CSV` remains available for trusted local
exports. Provider results are explicit `SUCCESS`, `EMPTY`, `ERROR`, or
`UNAVAILABLE` outcomes; each persisted bar records its actual source,
`FINAL`/`INTRADAY`/`UNKNOWN` status, and UTC `fetched_at`. A fallback result
retains the primary failure reason. Incremental updates begin at the latest
stored `symbol`/`datetime` and the database unique constraint prevents
duplicate bars; the latest date is requested again so an unfinished intraday
bar can be replaced by a later final bar. The project does not fabricate holidays or treat a
failed/unknown source as trading data.

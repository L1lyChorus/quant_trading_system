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

## Checks

```bash
pytest -q
python main.py
```


# tqqq-automated-trader (starter repo)

Lightweight starter repo for a production-oriented automated trading system focused on TQQQ.
This package is *daily-only* (Polygon.io daily bars), includes a `.env.example`, and a **mocked IB adapter**
so you can run the example without TWS/Gateway.

## Quickstart

1. Copy `.env.example` to `.env` and set `POLYGON_API_KEY`.
2. Create a Python 3.10+ virtualenv and install requirements:
   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Fetch daily data:
   ```
   python src/cli.py update-data --symbol TQQQ
   ```
4. Run a backtest:
   ```
   python src/cli.py backtest --config configs/example_daily.yaml
   ```

Files:
- `src/data/polygon_client.py` — daily data fetcher with parquet cache
- `src/engine/backtest.py` — simple vectorized backtest
- `src/strategies/*` — 3 example strategies
- `src/execution/ib_adapter.py` — MOCK IB adapter (safe, no live orders)
- `configs/example_daily.yaml` — example config
- `.env.example` — environment variables example

This repo is intentionally minimal. Use it as a scaffold to expand to minute-level data, IB live connectivity, advanced backtesting libraries, and CI.

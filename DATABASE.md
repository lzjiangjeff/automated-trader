# Database Documentation

## Overview

The system uses SQLite to store all backtest results, allowing you to:
- Review past backtest runs
- Compare performance across different configurations
- Generate graphs from stored data
- Track backtest history

## Database Schema

### backtest_runs
Stores metadata about each backtest run:
- `id`: Primary key
- `timestamp`: When the backtest was run
- `config_path`: Path to config file used
- `config_json`: Full configuration as JSON
- `start_date`: Backtest start date
- `end_date`: Backtest end date
- `symbol`: Symbol traded
- `initial_capital`: Starting capital
- `final_equity`: Ending equity
- `status`: Backtest status

### equity_curve
Stores daily equity values:
- `id`: Primary key
- `backtest_id`: Foreign key to backtest_runs
- `date`: Date
- `equity`: Equity value

### returns
Stores daily returns:
- `id`: Primary key
- `backtest_id`: Foreign key to backtest_runs
- `date`: Date
- `return_pct`: Return percentage

### trades
Stores all trades:
- `id`: Primary key
- `backtest_id`: Foreign key to backtest_runs
- `entry_date`: Trade entry date
- `exit_date`: Trade exit date
- `side`: 'long' or 'short'
- `shares`: Number of shares
- `entry_price`: Entry price
- `exit_price`: Exit price
- `stop_price`: Stop price
- `exit_reason`: Reason for exit
- `pnl`: Profit/loss
- `r_multiple`: R multiple
- `bars_in_trade`: Number of bars in trade
- `strategy`: Strategy name

### metrics
Stores performance metrics:
- `id`: Primary key
- `backtest_id`: Foreign key to backtest_runs
- `metric_name`: Metric name (e.g., 'cagr', 'sharpe')
- `metric_value`: Metric value

## Usage

### Automatic Saving

Backtests are automatically saved to the database when you run:
```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml
```

The database file is located at: `data/backtests.db`

### Listing Backtests

```bash
python cli.py list-backtests --limit 20
```

### Reviewing a Backtest

```bash
python cli.py review --id 1
```

### Generating Graphs

```bash
python cli.py visualize --id 1 --output out/review/
```

This will:
1. Load the backtest data from the database
2. Fetch price data for the backtest period
3. Generate all graphs and reports
4. Save to the specified output directory

## Database Location

By default, the database is stored at:
- `data/backtests.db`

You can modify this by changing the `db_path` parameter when initializing `BacktestDatabase`.

## Querying the Database

You can directly query the SQLite database using any SQLite client:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/backtests.db')

# Get all backtest runs
runs = pd.read_sql_query("SELECT * FROM backtest_runs", conn)

# Get equity curve for a specific backtest
equity = pd.read_sql_query(
    "SELECT * FROM equity_curve WHERE backtest_id = 1",
    conn
)

# Get all trades for a backtest
trades = pd.read_sql_query(
    "SELECT * FROM trades WHERE backtest_id = 1",
    conn
)

# Get metrics for a backtest
metrics = pd.read_sql_query(
    "SELECT * FROM metrics WHERE backtest_id = 1",
    conn
)

conn.close()
```

## Maintenance

### Backing Up

Simply copy the `data/backtests.db` file to backup your database.

### Deleting Backtests

You can delete a backtest and all associated data:

```python
from data.database import BacktestDatabase

db = BacktestDatabase()
db.delete_backtest(backtest_id=1)
```

### Database Size

The database will grow over time as you run more backtests. To manage size:
1. Periodically delete old backtests
2. Archive the database file
3. Use database compression tools

## Performance

SQLite is suitable for storing backtest results because:
- Backtest data is written once and read many times
- Data size is manageable (typically < 100MB for hundreds of backtests)
- No concurrent writes during backtesting
- Easy to backup and transfer

For very large datasets or high concurrency, consider migrating to PostgreSQL or another database system.


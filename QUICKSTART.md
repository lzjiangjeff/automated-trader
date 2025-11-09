# Quick Start Guide

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install TA-Lib (Optional but Recommended)

TA-Lib provides optimized technical indicators. Installation varies by platform:

**Windows:**
- Download pre-built wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
- Install: `pip install TA_Lib‑0.4.28‑cp39‑cp39‑win_amd64.whl` (adjust for your Python version)

**macOS:**
```bash
brew install ta-lib
pip install TA-Lib
```

**Linux:**
```bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
```

**Note:** If TA-Lib is not available, the system will use fallback implementations, but performance may be slower.

### 3. Interactive Brokers Setup (For Live Trading)

1. Install IBKR TWS or IB Gateway
2. Enable API access in TWS/Gateway settings
3. Set port (7497 for paper, 7496 for live)
4. Ensure TWS/Gateway is running before starting live trading

## Running Backtests

### Basic Backtest

```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml
```

### Custom Date Range

```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml --start 2020-01-01 --end 2024-01-01
```

### Custom Output Directory

```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml --charts out/my_backtest/
```

## Running Live Trading

### Paper Trading

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode paper --ibkr-host 127.0.0.1 --ibkr-port 7497
```

### Live Trading (Use with Caution!)

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode live --risk-guard
```

## Configuration

Edit `configs/tqqq_ensemble.yaml` to:
- Enable/disable strategies
- Adjust risk parameters
- Modify strategy parameters
- Set walk-forward windows
- Configure costs and slippage

## Output Files

After running a backtest, check the `out/` directory for:
- `report.html` - Comprehensive HTML report
- `equity_curve.png` - Equity curve chart
- `drawdown.png` - Drawdown chart
- `price_signals.png` - Price chart with signals
- `rolling_sharpe.png` - Rolling Sharpe ratio
- `trade_distribution.png` - Trade statistics
- `trade_log.csv` - Detailed trade log
- `metrics.json` - Performance metrics

**Note:** All backtest results are also automatically saved to the SQLite database at `data/backtests.db`. You can review and regenerate graphs from stored backtests at any time.

## Troubleshooting

### Data Fetching Issues
- Check internet connection
- Verify symbol names are correct
- Clear cache: delete `data/` directory

### TA-Lib Issues
- System will fall back to Python implementations if TA-Lib is not available
- Performance may be slower but functionality remains

### IBKR Connection Issues
- Ensure TWS/Gateway is running
- Check port numbers (7497 for paper, 7496 for live)
- Verify API access is enabled in TWS/Gateway

## Reviewing Stored Backtests

All backtests are automatically saved to a SQLite database (`data/backtests.db`).

### List Stored Backtests

```bash
python cli.py list-backtests --limit 20
```

### Review a Specific Backtest

```bash
python cli.py review --id 1
```

This shows:
- Backtest metadata (timestamp, config, symbol, period)
- Performance metrics (CAGR, Sharpe, drawdown, etc.)
- Trade statistics

### Generate Graphs from Database

```bash
python cli.py visualize --id 1 --output out/review/
```

This will:
1. Load the backtest data from the database
2. Fetch price data for the period
3. Generate all graphs and reports
4. Save to the specified directory

## Next Steps

1. Review the example configurations in `configs/`
2. Run backtests on different time periods
3. Analyze results in the generated reports
4. Review stored backtests using the database commands
5. Compare performance across different configurations
6. Adjust strategy parameters based on backtest results
7. Test with paper trading before going live

## Important Notes

⚠️ **Research Only / Not Financial Advice**

- This system is for research and educational purposes only
- Past performance does not guarantee future results
- Trading involves substantial risk of loss
- Always test thoroughly before live trading
- Use paper trading to validate strategies

## Support

For issues and questions:
1. Check the README.md for detailed documentation
2. Review configuration files for parameter explanations
3. Examine backtest reports for performance insights


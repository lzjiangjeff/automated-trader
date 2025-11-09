# Auto Trader Agent - TQQQ Trading System

A comprehensive quantitative trading system for TQQQ with multiple strategies, rigorous backtesting, and live execution via Interactive Brokers.

## ⚠️ DISCLAIMER

**Research Only / Not Financial Advice**

This system is for research and educational purposes only. Trading involves substantial risk of loss. Past performance does not guarantee future results.

## Features

- **Multiple Trading Strategies**: Trend-EMA, Breakout-Momentum, Mean-Reversion, Volatility Overlay, Regime Filter
- **Robust Backtesting**: Walk-forward validation, out-of-sample testing, stress tests
- **Risk Management**: Position sizing, stops, drawdown controls, exposure limits
- **Live Trading**: Interactive Brokers integration with paper and live trading modes
- **Comprehensive Reporting**: Performance metrics, charts, trade logs

## Installation

```bash
pip install -r requirements.txt
```

Note: TA-Lib requires additional system dependencies. See [TA-Lib installation guide](https://github.com/mrjbq7/ta-lib).

## Quick Start

### Backtest

```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml --start 2012-01-01 --end 2025-11-08 --walk-forward 3y-1y --report out/report.html --charts out/
```

### Paper Trading

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode paper --ibkr-host 127.0.0.1 --ibkr-port 7497
```

### Live Trading

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode live --risk-guard on
```

### Review Stored Backtests

List all stored backtests:
```bash
python cli.py list-backtests
```

Review a specific backtest:
```bash
python cli.py review --id 1
```

Generate graphs for a stored backtest:
```bash
python cli.py visualize --id 1 --output out/review/
```

## Project Structure

```
auto-trader-agent/
├── configs/           # Configuration files
├── data/              # Data cache
├── strategies/        # Trading strategies
├── backtesting/       # Backtesting engine
├── execution/         # IBKR execution
├── risk/              # Risk management
├── reporting/         # Reporting and visualization
├── utils/             # Utilities
└── cli.py            # CLI interface
```

## Configuration

See `configs/` directory for example configurations. Each config file controls:
- Strategy selection and parameters
- Risk limits
- Walk-forward windows
- Costs and slippage
- Reporting options

## License

MIT License - See LICENSE file for details


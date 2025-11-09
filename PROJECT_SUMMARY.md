# Project Summary

## Overview

This is a comprehensive quantitative trading system for TQQQ (3x leveraged QQQ ETF) that includes:

1. **Multiple Trading Strategies**
2. **Robust Backtesting Engine**
3. **Risk Management System**
4. **Live Trading via Interactive Brokers**
5. **Comprehensive Reporting and Visualization**

## Project Structure

```
auto-trader-agent/
├── configs/              # Configuration files (YAML)
│   ├── tqqq_ensemble.yaml
│   ├── tqqq_trend_only.yaml
│   └── tqqq_mr_only.yaml
├── data/                 # Data fetching and feature engineering
│   ├── fetcher.py       # Yahoo Finance data fetching
│   └── features.py      # Technical indicator calculation
├── strategies/           # Trading strategies
│   ├── base.py          # Base strategy class
│   ├── trend_ema.py     # Trend following strategy
│   ├── breakout_momentum.py
│   ├── mean_reversion.py
│   ├── volatility_overlay.py
│   ├── regime_filter.py
│   └── ensemble.py      # Ensemble strategy
├── risk/                 # Risk management
│   ├── manager.py       # Risk manager
│   └── position_sizing.py
├── backtesting/          # Backtesting engine
│   └── engine.py
├── reporting/            # Reporting and visualization
│   └── reporter.py
├── execution/            # Live trading execution
│   └── ibkr_executor.py
├── utils/                # Utilities
│   └── config.py        # Configuration management
├── cli.py               # Command-line interface
├── requirements.txt     # Python dependencies
└── README.md            # Documentation
```

## Key Features

### 1. Trading Strategies

- **Trend-EMA**: EMA crossover strategy with RSI confirmation
- **Breakout-Momentum**: Breakout strategy with volume and ADX confirmation
- **Mean-Reversion**: Mean reversion strategy for non-trending markets
- **Volatility Overlay**: Position sizing based on volatility
- **Regime Filter**: Market regime detection (risk-on/risk-off)
- **Ensemble**: Weighted combination of multiple strategies

### 2. Risk Management

- Position sizing based on ATR stop distance
- Per-trade risk limits (default: 1% of equity)
- Portfolio exposure caps (net: -100% to +150%, gross: ≤200%)
- Stop losses (ATR-based, default: 2.5x ATR)
- Trailing stops
- Time-based stops
- Daily loss limits
- Maximum drawdown controls
- Drawdown recovery mechanisms

### 3. Backtesting

- Event-driven backtesting engine
- Walk-forward validation support
- Realistic cost modeling (commissions, slippage, market impact)
- Multiple benchmark comparisons
- Comprehensive performance metrics

### 4. Reporting

- Equity curve visualization
- Drawdown charts
- Price charts with buy/sell markers
- Rolling Sharpe ratio
- Trade distribution analysis
- Detailed trade logs (CSV)
- Performance metrics (JSON)
- HTML reports

### 5. Live Trading

- Interactive Brokers integration
- Paper and live trading modes
- Real-time risk monitoring
- Kill switch mechanism
- Position management
- Order execution

## Configuration

All settings are controlled via YAML configuration files:

- Strategy selection and parameters
- Risk limits
- Walk-forward windows
- Costs and slippage
- Reporting options
- Execution settings

## Usage

### Backtest

```bash
python cli.py backtest --config configs/tqqq_ensemble.yaml --start 2012-01-01 --end 2025-11-08
```

### Paper Trading

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode paper --ibkr-host 127.0.0.1 --ibkr-port 7497
```

### Live Trading

```bash
python cli.py trade --config configs/tqqq_ensemble.yaml --mode live --risk-guard
```

## Performance Metrics

The system calculates and reports:

- CAGR (Compound Annual Growth Rate)
- Total Return
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Maximum Drawdown
- Average Drawdown
- Volatility
- Win Rate
- Profit Factor
- Trade Count
- Average R Multiple
- Net/Gross Exposure
- Turnover
- Best/Worst Day
- Skewness and Kurtosis

## Data Sources

- **Primary**: TQQQ (3x leveraged QQQ)
- **Context**: QQQ, VIX, US10Y yield
- **Source**: Yahoo Finance (via yfinance)

## Technical Indicators

- EMAs (8, 21, 50)
- SMAs (50, 200)
- RSI (14)
- MACD
- ADX (14)
- ATR (14)
- Bollinger Bands
- Realized Volatility
- Relative Volume
- Rolling Skewness/Kurtosis

## Risk Considerations

⚠️ **Important Notes:**

1. TQQQ is a 3x leveraged ETF - extremely volatile
2. Drawdown control is the #1 priority
3. Past performance does not guarantee future results
4. Always test with paper trading before going live
5. Use appropriate position sizing
6. Monitor risk metrics continuously

## Dependencies

- pandas >= 2.0.0
- numpy >= 1.24.0
- yfinance >= 0.2.28
- matplotlib >= 3.7.0
- seaborn >= 0.12.0
- pyyaml >= 6.0
- pydantic >= 2.0.0
- click >= 8.1.0
- ib-insync >= 0.9.86 (optional, for live trading)
- ta-lib (optional, for better performance)

## Future Enhancements

Potential improvements:

1. Walk-forward optimization
2. Hyperparameter optimization (Optuna)
3. Machine learning strategies
4. Additional technical indicators
5. Multi-timeframe analysis
6. Portfolio optimization
7. Real-time data feeds
8. Advanced order types
9. Performance attribution
10. Strategy correlation analysis

## License

MIT License - See LICENSE file for details

## Disclaimer

**Research Only / Not Financial Advice**

This system is for research and educational purposes only. Trading involves substantial risk of loss. Past performance does not guarantee future results.


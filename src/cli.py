import sys
import os
import argparse
import yaml
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.data.polygon_client import PolygonClient
from src.backtest.backtester import Backtester


def cmd_update_data(args):
    """
    Download and cache historical data for a symbol using Polygon.io
    """
    client = PolygonClient()
    client.update_data(symbol=args.symbol)


def cmd_backtest(args):
    """
    Run backtests for all strategies and print summary metrics.
    """
    # Load config
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)

    symbol = cfg['data']['symbol']
    client = PolygonClient()
    df = client.load_cached(symbol=symbol)

    bt = Backtester(df, config=cfg)
    results = bt.run_all()

    print("\n--- Backtest summary ---")
    for strat, res in results.items():
        m = res['metrics']
        print(f"Strategy: {strat}")
        print(f"  total_return: {m['total_return']}")
        print(f"  ann_return: {m['ann_return']}")
        print(f"  sharpe: {m['sharpe']}")
        print(f"  max_drawdown: {m['max_drawdown']}\n")


def cmd_plot_results(args):
    """
    Plot equity curves, drawdowns, and display risk metrics.
    """
    # Load config
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)

    symbol = cfg['data']['symbol']
    client = PolygonClient()
    df = client.load_cached(symbol=symbol)

    bt = Backtester(df, config=cfg)
    results = bt.run_all_strategies()

    # Plot equity curves
    plt.figure(figsize=(12, 6))
    for strat, res in results.items():
        res['equity_curve']['equity'].plot(label=strat)
    plt.title(f"{symbol} Strategy Equity Curves")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # Plot drawdowns
    plt.figure(figsize=(12, 6))
    for strat, res in results.items():
        drawdown = res['equity_curve']['equity'] / res['equity_curve']['equity'].cummax() - 1
        drawdown.plot(label=strat)
    plt.title(f"{symbol} Strategy Drawdowns")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # Print metrics table
    metrics_data = []
    for strat, res in results.items():
        m = res['metrics']
        metrics_data.append({
            "Strategy": strat,
            "Total Return": f"{m['total_return']*100:.2f}%",
            "Annualized Return": f"{m['ann_return']*100:.2f}%",
            "Sharpe": f"{m['sharpe']:.2f}",
            "Max Drawdown": f"{m['max_drawdown']*100:.2f}%"
        })

    df_metrics = pd.DataFrame(metrics_data)
    print("\n=== Risk Metrics Summary ===")
    print(df_metrics.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(prog="tqqq-trader")
    subparsers = parser.add_subparsers(dest="command")

    # update-data
    p_update = subparsers.add_parser("update-data", help="Download and cache historical data")
    p_update.add_argument("--symbol", required=True, help="Symbol to update (e.g. TQQQ)")
    p_update.set_defaults(func=cmd_update_data)

    # backtest
    p_backtest = subparsers.add_parser("backtest", help="Run backtest and print summary")
    p_backtest.add_argument("--config", required=True, help="Path to YAML config file")
    p_backtest.set_defaults(func=cmd_backtest)

    # plot-results
    p_plot = subparsers.add_parser("plot-results", help="Plot equity curves, drawdowns, and metrics")
    p_plot.add_argument("--config", required=True, help="Path to YAML config file")
    p_plot.set_defaults(func=cmd_plot_results)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

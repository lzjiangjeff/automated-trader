"""Reporting and visualization module."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
from typing import Dict, Optional, List
import json
from datetime import datetime

# Set style
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except:
    try:
        plt.style.use('seaborn-darkgrid')
    except:
        plt.style.use('default')
sns.set_palette("husl")


class Reporter:
    """Generates reports and charts for backtest results."""
    
    def __init__(self, output_dir: str = "out/"):
        """Initialize reporter.
        
        Args:
            output_dir: Output directory for reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        results: Dict,
        price_df: pd.DataFrame,
        config: Optional[Dict] = None,
        benchmark_df: Optional[pd.DataFrame] = None
    ) -> str:
        """Generate comprehensive report.
        
        Args:
            results: Backtest results dictionary
            price_df: Price DataFrame
            config: Configuration dictionary
            benchmark_df: Optional benchmark DataFrame
        
        Returns:
            Path to generated report
        """
        # Generate charts
        if 'equity_curve' in results:
            self._plot_equity_curve(results, benchmark_df)
            self._plot_drawdown(results)
            self._plot_price_with_signals(results, price_df)
            self._plot_rolling_sharpe(results)
            self._plot_trade_distribution(results)
        
        # Save trade log
        if 'trade_log' in results and len(results['trade_log']) > 0:
            self._save_trade_log(results['trade_log'])
        
        # Save metrics
        if 'metrics' in results:
            self._save_metrics(results['metrics'])
            self._generate_html_report(results, price_df, config)
        
        return str(self.output_dir)
    
    def _plot_equity_curve(self, results: Dict, benchmark_df: Optional[pd.DataFrame] = None):
        """Plot equity curve."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        equity_curve = results['equity_curve']
        ax.plot(equity_curve.index, equity_curve.values, label='Strategy', linewidth=2)
        
        if benchmark_df is not None and 'close' in benchmark_df.columns:
            # Normalize benchmark
            initial_value = equity_curve.iloc[0]
            benchmark_normalized = benchmark_df['close'] / benchmark_df['close'].iloc[0] * initial_value
            common_dates = equity_curve.index.intersection(benchmark_normalized.index)
            if len(common_dates) > 0:
                ax.plot(
                    common_dates,
                    benchmark_normalized.loc[common_dates],
                    label='Benchmark (Buy & Hold)',
                    linewidth=2,
                    alpha=0.7
                )
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Equity ($)', fontsize=12)
        ax.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(self.output_dir / 'equity_curve.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown(self, results: Dict):
        """Plot drawdown curve."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        equity_curve = results['equity_curve']
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max * 100
        
        ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color='red')
        ax.plot(drawdown.index, drawdown.values, linewidth=2, color='red')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.set_title('Underwater Chart (Drawdown)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(self.output_dir / 'drawdown.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_price_with_signals(self, results: Dict, price_df: pd.DataFrame):
        """Plot price chart with buy/sell signals."""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plot price
        ax.plot(price_df.index, price_df['close'], label='Price', linewidth=1.5, alpha=0.7)
        
        # Plot signals from trade log
        if 'trade_log' in results:
            trade_log = results['trade_log']
            
            long_entries = [
                (pd.to_datetime(t['entry_date']), t['entry_price'])
                for t in trade_log if t['side'] == 'long'
            ]
            long_exits = [
                (pd.to_datetime(t['exit_date']), t['exit_price'])
                for t in trade_log if t['side'] == 'long'
            ]
            short_entries = [
                (pd.to_datetime(t['entry_date']), t['entry_price'])
                for t in trade_log if t['side'] == 'short'
            ]
            short_exits = [
                (pd.to_datetime(t['exit_date']), t['exit_price'])
                for t in trade_log if t['side'] == 'short'
            ]
            
            if long_entries:
                dates, prices = zip(*long_entries)
                ax.scatter(dates, prices, color='green', marker='^', s=100, label='Long Entry', zorder=5)
            
            if long_exits:
                dates, prices = zip(*long_exits)
                ax.scatter(dates, prices, color='red', marker='v', s=100, label='Long Exit', zorder=5)
            
            if short_entries:
                dates, prices = zip(*short_entries)
                ax.scatter(dates, prices, color='red', marker='v', s=100, label='Short Entry', zorder=5)
            
            if short_exits:
                dates, prices = zip(*short_exits)
                ax.scatter(dates, prices, color='green', marker='^', s=100, label='Short Exit', zorder=5)
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Price ($)', fontsize=12)
        ax.set_title('Price Chart with Trading Signals', fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(self.output_dir / 'price_signals.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_rolling_sharpe(self, results: Dict, window: int = 252):
        """Plot rolling Sharpe ratio."""
        if 'returns' not in results:
            return
        
        returns = results['returns']
        
        if len(returns) < window:
            return
        
        rolling_sharpe = returns.rolling(window=window).mean() / returns.rolling(window=window).std() * np.sqrt(252)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(rolling_sharpe.index, rolling_sharpe.values, linewidth=2)
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Rolling Sharpe Ratio (252 days)', fontsize=12)
        ax.set_title('Rolling Sharpe Ratio', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(self.output_dir / 'rolling_sharpe.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_trade_distribution(self, results: Dict):
        """Plot trade distribution."""
        if 'trade_log' not in results or len(results['trade_log']) == 0:
            return
        
        trade_log = results['trade_log']
        pnls = [t['pnl'] for t in trade_log]
        r_multiples = [t['r_multiple'] for t in trade_log]
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # P&L distribution
        axes[0, 0].hist(pnls, bins=50, edgecolor='black', alpha=0.7)
        axes[0, 0].axvline(x=0, color='red', linestyle='--', linewidth=2)
        axes[0, 0].set_xlabel('P&L ($)', fontsize=10)
        axes[0, 0].set_ylabel('Frequency', fontsize=10)
        axes[0, 0].set_title('P&L Distribution', fontsize=12, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3)
        
        # R-multiple distribution
        axes[0, 1].hist(r_multiples, bins=50, edgecolor='black', alpha=0.7)
        axes[0, 1].axvline(x=0, color='red', linestyle='--', linewidth=2)
        axes[0, 1].set_xlabel('R Multiple', fontsize=10)
        axes[0, 1].set_ylabel('Frequency', fontsize=10)
        axes[0, 1].set_title('R-Multiple Distribution', fontsize=12, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Monthly returns
        if 'returns' in results:
            returns = results['returns']
            monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
            axes[1, 0].bar(range(len(monthly_returns)), monthly_returns.values * 100, alpha=0.7)
            axes[1, 0].axhline(y=0, color='black', linestyle='-', linewidth=1)
            axes[1, 0].set_xlabel('Month', fontsize=10)
            axes[1, 0].set_ylabel('Return (%)', fontsize=10)
            axes[1, 0].set_title('Monthly Returns', fontsize=12, fontweight='bold')
            axes[1, 0].grid(True, alpha=0.3)
        
        # Trade duration
        durations = [t['bars_in_trade'] for t in trade_log]
        axes[1, 1].hist(durations, bins=30, edgecolor='black', alpha=0.7)
        axes[1, 1].set_xlabel('Bars in Trade', fontsize=10)
        axes[1, 1].set_ylabel('Frequency', fontsize=10)
        axes[1, 1].set_title('Trade Duration Distribution', fontsize=12, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'trade_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _save_trade_log(self, trade_log: List[Dict]):
        """Save trade log to CSV."""
        df = pd.DataFrame(trade_log)
        df.to_csv(self.output_dir / 'trade_log.csv', index=False)
    
    def _save_metrics(self, metrics: Dict):
        """Save metrics to JSON."""
        with open(self.output_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def _generate_html_report(
        self,
        results: Dict,
        price_df: pd.DataFrame,
        config: Optional[Dict] = None
    ):
        """Generate HTML report."""
        metrics = results.get('metrics', {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .metric {{ font-weight: bold; color: #4CAF50; }}
                .warning {{ color: #ff9800; }}
                .danger {{ color: #f44336; }}
                img {{ max-width: 100%; height: auto; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Backtest Report</h1>
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Disclaimer</h2>
            <p class="warning"><strong>Research Only / Not Financial Advice</strong></p>
            <p>This report is for research and educational purposes only. Past performance does not guarantee future results.</p>
            
            <h2>Performance Metrics</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>CAGR</td>
                    <td class="metric">{metrics.get('cagr', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Total Return</td>
                    <td class="metric">{metrics.get('total_return', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Sharpe Ratio</td>
                    <td class="metric">{metrics.get('sharpe', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Sortino Ratio</td>
                    <td class="metric">{metrics.get('sortino', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Calmar Ratio</td>
                    <td class="metric">{metrics.get('calmar', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Max Drawdown</td>
                    <td class="{'danger' if metrics.get('max_drawdown', 0) < -40 else 'metric'}">{metrics.get('max_drawdown', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Average Drawdown</td>
                    <td>{metrics.get('avg_drawdown', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Volatility</td>
                    <td>{metrics.get('volatility', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Win Rate</td>
                    <td>{metrics.get('win_rate', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Profit Factor</td>
                    <td>{metrics.get('profit_factor', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Trade Count</td>
                    <td>{metrics.get('trade_count', 0)}</td>
                </tr>
                <tr>
                    <td>Average R Multiple</td>
                    <td>{metrics.get('avg_r_multiple', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Net Exposure</td>
                    <td>{metrics.get('net_exposure', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Gross Exposure</td>
                    <td>{metrics.get('gross_exposure', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Turnover</td>
                    <td>{metrics.get('turnover', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Best Day</td>
                    <td class="metric">{metrics.get('best_day', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Worst Day</td>
                    <td class="danger">{metrics.get('worst_day', 0):.2f}%</td>
                </tr>
                <tr>
                    <td>Skewness</td>
                    <td>{metrics.get('skew', 0):.2f}</td>
                </tr>
                <tr>
                    <td>Kurtosis</td>
                    <td>{metrics.get('kurtosis', 0):.2f}</td>
                </tr>
            </table>
            
            <h2>Charts</h2>
            <img src="equity_curve.png" alt="Equity Curve">
            <img src="drawdown.png" alt="Drawdown">
            <img src="price_signals.png" alt="Price with Signals">
            <img src="rolling_sharpe.png" alt="Rolling Sharpe">
            <img src="trade_distribution.png" alt="Trade Distribution">
            
            <h2>Trade Log</h2>
            <p>See <a href="trade_log.csv">trade_log.csv</a> for detailed trade information.</p>
            
            <h2>Metrics</h2>
            <p>See <a href="metrics.json">metrics.json</a> for raw metrics data.</p>
        </body>
        </html>
        """
        
        with open(self.output_dir / 'report.html', 'w') as f:
            f.write(html)


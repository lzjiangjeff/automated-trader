"""Command-line interface for the trading system."""

import click
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from utils.config import load_config, Config
from data.fetcher import DataFetcher
from data.features import FeatureEngineer
from strategies.trend_ema import TrendEMAStrategy
from strategies.breakout_momentum import BreakoutMomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.volatility_overlay import VolatilityOverlayStrategy
from strategies.regime_filter import RegimeFilterStrategy
from strategies.ensemble import EnsembleStrategy
from backtesting.engine import BacktestEngine
from reporting.reporter import Reporter
from execution.ibkr_executor import IBKRExecutor
from data.database import BacktestDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_strategies(config: Config) -> list:
    """Create strategy instances from config.
    
    Args:
        config: Configuration object
    
    Returns:
        List of strategy instances
    """
    strategies = []
    
    # Trend EMA
    if config.strategies.trend_ema.enabled:
        strategies.append(TrendEMAStrategy(config.strategies.trend_ema.model_dump()))
    
    # Breakout Momentum
    if config.strategies.breakout_momentum.enabled:
        strategies.append(BreakoutMomentumStrategy(config.strategies.breakout_momentum.model_dump()))
    
    # Mean Reversion
    if config.strategies.mean_reversion.enabled:
        strategies.append(MeanReversionStrategy(config.strategies.mean_reversion.model_dump()))
    
    # Volatility Overlay
    if config.strategies.volatility_overlay.enabled:
        strategies.append(VolatilityOverlayStrategy(config.strategies.volatility_overlay.model_dump()))
    
    # Regime Filter
    if config.strategies.regime_filter.enabled:
        strategies.append(RegimeFilterStrategy(config.strategies.regime_filter.model_dump()))
    
    return strategies


@click.group()
def cli():
    """TQQQ Trading System CLI."""
    pass


@cli.command()
@click.option('--config', required=True, help='Path to config file')
@click.option('--start', help='Start date (YYYY-MM-DD)')
@click.option('--end', help='End date (YYYY-MM-DD)')
@click.option('--walk-forward', help='Walk-forward specification (e.g., 3y-1y)')
@click.option('--report', help='Report output path')
@click.option('--charts', help='Charts output directory')
def backtest(config: str, start: Optional[str], end: Optional[str], walk_forward: Optional[str], report: Optional[str], charts: Optional[str]):
    """Run backtest."""
    logger.info("Starting backtest...")
    
    # Load config
    cfg = load_config(config)
    
    # Override dates if provided
    if start:
        cfg.data.start_date = start
    if end:
        cfg.data.end_date = end
    
    # Override report paths if provided
    if report:
        cfg.reporting.output_dir = str(Path(report).parent)
    if charts:
        cfg.reporting.output_dir = charts
    
    # Create strategies
    strategies = create_strategies(cfg)
    
    # Fetch data
    logger.info("Fetching data...")
    fetcher = DataFetcher(cache_dir=cfg.data.cache_dir)
    
    # Fetch primary symbol
    primary_data = fetcher.fetch_symbol(
        symbol=cfg.symbol.primary,
        start_date=cfg.data.start_date,
        end_date=cfg.data.end_date,
        interval=cfg.data.interval
    )
    
    # Fetch context symbols
    context_data = {}
    for symbol in cfg.symbol.context:
        try:
            context_data[symbol] = fetcher.fetch_symbol(
                symbol=symbol,
                start_date=cfg.data.start_date,
                end_date=cfg.data.end_date,
                interval=cfg.data.interval
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol}: {e}")
    
    # Engineer features
    logger.info("Engineering features...")
    feature_engineer = FeatureEngineer()
    primary_data = feature_engineer.calculate_all_features(primary_data)
    
    for symbol in context_data:
        context_data[symbol] = feature_engineer.calculate_all_features(context_data[symbol])
    
    # Run backtest
    logger.info("Running backtest...")
    engine = BacktestEngine(cfg, strategies, save_to_db=True)
    results = engine.run(primary_data, context_data)
    
    # Update database with config path if backtest was saved
    if 'backtest_id' in results and results['backtest_id']:
        db = BacktestDatabase()
        # Update config path in database
        conn = db.db_path  # Get db path, we'll update via SQL
        import sqlite3
        conn_sql = sqlite3.connect(db.db_path)
        cursor = conn_sql.cursor()
        cursor.execute("UPDATE backtest_runs SET config_path = ? WHERE id = ?", (config, results['backtest_id']))
        conn_sql.commit()
        conn_sql.close()
        logger.info(f"Backtest saved to database with ID: {results['backtest_id']}")
    
    # Fetch benchmark data if specified
    benchmark_data = None
    if cfg.backtesting.benchmark_symbols:
        benchmark_symbol = cfg.backtesting.benchmark_symbols[0]  # Use first benchmark
        try:
            benchmark_data = fetcher.fetch_symbol(
                symbol=benchmark_symbol,
                start_date=cfg.data.start_date,
                end_date=cfg.data.end_date,
                interval=cfg.data.interval
            )
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark {benchmark_symbol}: {e}")
    
    # Generate report
    logger.info("Generating report...")
    reporter = Reporter(output_dir=cfg.reporting.output_dir)
    reporter.generate_report(results, primary_data, cfg.model_dump(), benchmark_data)
    
    # Print summary
    if 'metrics' in results:
        metrics = results['metrics']
        logger.info("\n" + "="*50)
        logger.info("BACKTEST RESULTS")
        logger.info("="*50)
        logger.info(f"Backtest ID: {results.get('backtest_id', 'N/A')}")
        logger.info(f"CAGR: {metrics.get('cagr', 0):.2f}%")
        logger.info(f"Total Return: {metrics.get('total_return', 0):.2f}%")
        logger.info(f"Sharpe Ratio: {metrics.get('sharpe', 0):.2f}")
        logger.info(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
        logger.info(f"Win Rate: {metrics.get('win_rate', 0):.2f}%")
        logger.info(f"Trade Count: {metrics.get('trade_count', 0)}")
        logger.info("="*50)
        logger.info(f"Report saved to: {cfg.reporting.output_dir}")
        if 'backtest_id' in results:
            logger.info(f"View this backtest later with: python cli.py review --id {results['backtest_id']}")
    
    logger.info("Backtest complete!")


@cli.command()
@click.option('--config', required=True, help='Path to config file')
@click.option('--mode', type=click.Choice(['paper', 'live']), default='paper', help='Trading mode')
@click.option('--ibkr-host', help='IBKR host')
@click.option('--ibkr-port', type=int, help='IBKR port')
@click.option('--risk-guard', is_flag=True, help='Enable risk guard')
def trade(config: str, mode: str, ibkr_host: Optional[str], ibkr_port: Optional[int], risk_guard: bool):
    """Run live trading."""
    logger.info(f"Starting {mode} trading...")
    
    # Load config
    cfg = load_config(config)
    
    # Override execution config
    cfg.execution.mode = mode
    if ibkr_host:
        cfg.execution.ibkr.host = ibkr_host
    if ibkr_port:
        cfg.execution.ibkr.port = ibkr_port
    if risk_guard:
        cfg.execution.risk_guard = True
    
    # Create strategies
    strategies = create_strategies(cfg)
    
    # Initialize IBKR executor
    try:
        executor = IBKRExecutor(cfg.execution.model_dump())
    except ImportError:
        logger.error("ib_insync not available. Install it with: pip install ib-insync")
        return
    
    # Connect to IBKR
    async def run_trading():
        connected = await executor.connect()
        if not connected:
            logger.error("Failed to connect to IBKR")
            return
        
        logger.info("Connected to IBKR. Starting trading loop...")
        
        # This is a simplified trading loop
        # In production, you would:
        # 1. Fetch real-time data
        # 2. Generate signals
        # 3. Check risk limits
        # 4. Place orders
        # 5. Monitor positions
        # 6. Handle errors and reconnect
        
        try:
            while True:
                # Health check
                if not await executor.health_check():
                    logger.error("Health check failed")
                    break
                
                # Get account value
                equity = await executor.get_account_value()
                logger.info(f"Account equity: ${equity:,.2f}")
                
                # Monitor risk
                # await executor.monitor_risk(equity, drawdown, daily_pnl)
                
                # Sleep for a bit (in production, this would be event-driven)
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Stopping trading...")
        finally:
            await executor.disconnect()
    
    # Run async trading loop
    asyncio.run(run_trading())


@cli.command()
@click.option('--limit', default=10, help='Number of backtests to list')
def list_backtests(limit: int):
    """List stored backtest runs."""
    logger.info("Fetching backtest runs...")
    
    db = BacktestDatabase()
    runs = db.get_backtest_runs(limit=limit)
    
    if runs.empty:
        logger.info("No backtests found in database.")
        return
    
    logger.info("\n" + "="*100)
    logger.info("STORED BACKTESTS")
    logger.info("="*100)
    
    for _, run in runs.iterrows():
        logger.info(f"ID: {run['id']} | {run['timestamp']} | {run['symbol']} | "
                   f"{run['start_date']} to {run['end_date'] or 'N/A'} | "
                   f"Capital: ${run['initial_capital']:,.0f} → ${run.get('final_equity', 0):,.0f}")
    
    logger.info("="*100)
    logger.info(f"\nView a backtest with: python cli.py review --id <ID>")
    logger.info(f"Generate graphs with: python cli.py visualize --id <ID>")


@cli.command()
@click.option('--id', 'backtest_id', required=True, type=int, help='Backtest ID')
def review(backtest_id: int):
    """Review a stored backtest."""
    logger.info(f"Loading backtest {backtest_id}...")
    
    db = BacktestDatabase()
    backtest_data = db.get_backtest_by_id(backtest_id)
    
    if not backtest_data:
        logger.error(f"Backtest {backtest_id} not found.")
        return
    
    run_info = backtest_data['run_info']
    metrics = backtest_data['metrics']
    
    logger.info("\n" + "="*50)
    logger.info(f"BACKTEST {backtest_id}")
    logger.info("="*50)
    logger.info(f"Timestamp: {run_info['timestamp']}")
    logger.info(f"Config: {run_info.get('config_path', 'N/A')}")
    logger.info(f"Symbol: {run_info['symbol']}")
    logger.info(f"Period: {run_info['start_date']} to {run_info.get('end_date', 'N/A')}")
    logger.info(f"Initial Capital: ${run_info['initial_capital']:,.2f}")
    logger.info(f"Final Equity: ${run_info.get('final_equity', 0):,.2f}")
    logger.info("\nPerformance Metrics:")
    logger.info(f"  CAGR: {metrics.get('cagr', 0):.2f}%")
    logger.info(f"  Total Return: {metrics.get('total_return', 0):.2f}%")
    logger.info(f"  Sharpe Ratio: {metrics.get('sharpe', 0):.2f}")
    logger.info(f"  Sortino Ratio: {metrics.get('sortino', 0):.2f}")
    logger.info(f"  Calmar Ratio: {metrics.get('calmar', 0):.2f}")
    logger.info(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
    logger.info(f"  Win Rate: {metrics.get('win_rate', 0):.2f}%")
    logger.info(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
    logger.info(f"  Trade Count: {metrics.get('trade_count', 0)}")
    logger.info(f"  Avg R Multiple: {metrics.get('avg_r_multiple', 0):.2f}")
    logger.info("="*50)


@cli.command()
@click.option('--id', 'backtest_id', required=True, type=int, help='Backtest ID')
@click.option('--output', help='Output directory for graphs')
def visualize(backtest_id: int, output: Optional[str]):
    """Generate graphs for a stored backtest."""
    logger.info(f"Generating graphs for backtest {backtest_id}...")
    
    db = BacktestDatabase()
    backtest_data = db.get_backtest_by_id(backtest_id)
    
    if not backtest_data:
        logger.error(f"Backtest {backtest_id} not found.")
        return
    
    # Set output directory
    output_dir = output or "out/"
    
    # Fetch price data for the backtest period
    run_info = backtest_data['run_info']
    symbol = run_info['symbol']
    start_date = run_info['start_date']
    end_date = run_info.get('end_date')
    
    logger.info(f"Fetching price data for {symbol} from {start_date} to {end_date}...")
    fetcher = DataFetcher()
    try:
        price_df = fetcher.fetch_symbol(symbol, start_date, end_date)
    except Exception as e:
        logger.error(f"Failed to fetch price data: {e}")
        return
    
    # Prepare results dictionary for reporter
    results = {
        'equity_curve': backtest_data['equity_curve'],
        'returns': backtest_data['returns'],
        'trade_log': backtest_data['trade_log'],
        'metrics': backtest_data['metrics']
    }
    
    # Generate report
    logger.info("Generating graphs...")
    reporter = Reporter(output_dir=output_dir)
    reporter.generate_report(results, price_df, None, None)
    
    logger.info(f"Graphs saved to: {output_dir}")
    logger.info(f"Open {output_dir}/report.html to view the full report.")


if __name__ == '__main__':
    cli()


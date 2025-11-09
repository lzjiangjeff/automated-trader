"""Backtesting engine."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from risk.manager import RiskManager, Trade
from risk.position_sizing import PositionSizer
from strategies.base import BaseStrategy
from strategies.trend_ema import TrendEMAStrategy
from strategies.breakout_momentum import BreakoutMomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.volatility_overlay import VolatilityOverlayStrategy
from strategies.regime_filter import RegimeFilterStrategy
from strategies.ensemble import EnsembleStrategy
from utils.config import Config
from data.database import BacktestDatabase


class BacktestEngine:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, config: Config, strategies: List[BaseStrategy], save_to_db: bool = True):
        """Initialize backtest engine."""
        self.config = config
        self.strategies = strategies
        self.risk_manager = RiskManager(config.risk.model_dump())
        self.position_sizer = PositionSizer(
            initial_capital=config.risk.initial_capital,
            per_trade_risk_pct=config.risk.per_trade_risk_pct,
            stop_atr_mult=config.risk.stop_atr_mult
        )
        
        # Costs
        self.commission_per_share = config.costs.commission_per_share
        self.slippage_bps = config.costs.slippage_bps
        self.market_impact_bps = config.costs.market_impact_bps
        
        # Results
        self.equity_curve: List[float] = []
        self.trade_log: List[Dict] = []
        
        # Database
        self.save_to_db = save_to_db
        self.db = BacktestDatabase() if save_to_db else None
        self.backtest_id: Optional[int] = None
    
    def run(
        self,
        df: pd.DataFrame,
        context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> Dict:
        """Run backtest.
        
        Args:
            df: Primary symbol DataFrame with features
            context: Optional context DataFrames
        
        Returns:
            Dictionary with backtest results
        """
        # Reset state
        self.risk_manager = RiskManager(self.config.risk.model_dump())
        self.equity_curve = [self.risk_manager.initial_capital]
        self.trade_log = []
        
        # Determine which strategy or strategies to use
        core_strategies: List[BaseStrategy] = []
        if self.config.strategies.ensemble.enabled:
            enabled_strategies = [s for s in self.strategies if getattr(s, 'enabled', True)]
            core_strategies = [EnsembleStrategy(
                self.config.strategies.ensemble.model_dump(),
                enabled_strategies
            )]
        else:
            for strategy in self.strategies:
                if isinstance(strategy, (VolatilityOverlayStrategy, RegimeFilterStrategy)):
                    continue
                if getattr(strategy, 'enabled', True):
                    core_strategies.append(strategy)

        if not core_strategies:
            raise ValueError("No active strategy found. Enable at least one strategy in config.")

        # Get volatility overlay and regime filter if enabled
        vol_overlay = None
        regime_filter = None
        
        if self.config.strategies.volatility_overlay.enabled:
            for strategy in self.strategies:
                if isinstance(strategy, VolatilityOverlayStrategy):
                    vol_overlay = strategy
                    break
        
        if self.config.strategies.regime_filter.enabled:
            for strategy in self.strategies:
                if isinstance(strategy, RegimeFilterStrategy):
                    regime_filter = strategy
                    break
        
        # Run backtest
        dates = df.index
        
        for i, date in enumerate(dates):
            if i < 50:  # Need enough data for indicators
                continue
            
            current_data = df.iloc[:i+1]
            current_row = df.iloc[i]
            
            # Update positions
            closed_trades = self.risk_manager.update_positions(
                date=date,
                current_price=current_row['close'],
                atr=current_row.get('atr', current_row['close'] * 0.02),
                high=current_row['high'],
                low=current_row['low']
            )

            # Trend-based exits before evaluating new entries
            for strategy in core_strategies:
                if hasattr(strategy, "should_exit") and self.risk_manager.positions:
                    strategy_name = strategy.__class__.__name__
                    if strategy.should_exit(current_data):
                        for trade in self.risk_manager.positions[:]:
                            if trade.strategy == strategy_name:
                                self.risk_manager.force_exit(trade, date, current_row['close'], "trend_break")
                                closed_trades.append(trade)
            
            # Log closed trades
            for trade in closed_trades:
                self._log_trade(trade, current_row['close'])
            
            # Generate signals for each core strategy
            for strategy in core_strategies:
                signals_df = strategy.generate_signals(current_data, context)
                if 'signal' not in signals_df.columns or len(signals_df) == 0:
                    continue
                
                signal = signals_df.iloc[-1]['signal']
                if signal == 0:
                    continue
                
                strategy_name = strategy.__class__.__name__
                
                # Determine whether this is a fresh entry or a pyramid add
                same_signal_trades = [
                    t for t in self.risk_manager.positions
                    if t.signal == signal and t.strategy == strategy_name
                ]
                is_pyramid = False
                pyramid_threshold = None
                if same_signal_trades:
                    pyramid_check = self.risk_manager.can_pyramid(signal, strategy_name)
                    if pyramid_check:
                        _, pyramid_threshold = pyramid_check
                        is_pyramid = True
                    else:
                        continue
                
                # Apply regime filter exposure
                exposure_mult = 1.0
                if regime_filter:
                    try:
                        exposure_mult_series = regime_filter.get_exposure_multiplier(
                            current_data, context
                        )
                        if len(exposure_mult_series) > 0:
                            exposure_mult = exposure_mult_series.iloc[-1]
                            if pd.isna(exposure_mult) or exposure_mult <= 0:
                                exposure_mult = 0.1
                    except Exception:
                        exposure_mult = 1.0
                
                # Check if we can enter trade
                if not self.risk_manager.can_enter_trade(
                    signal,
                    current_row['close'],
                    current_row.get('atr', current_row['close'] * 0.02)
                ):
                    continue
                
                # Calculate position size
                atr = current_row.get('atr', current_row['close'] * 0.02)
                atr_series = current_data['atr'].dropna()
                if len(atr_series) >= 50:
                    atr_percentile = float(atr_series.rank(pct=True).iloc[-1])
                else:
                    atr_percentile = 0.5
                atr_percentile = float(np.clip(atr_percentile, 0.0, 1.0))
                stop_mult = float(np.clip(1.8 + (1.0 - atr_percentile) * 0.8, 1.8, 2.6))
                trailing_mult = float(np.clip(1.0 + (1.0 - atr_percentile) * 0.2, 0.8, 1.2))
                
                # Get size multiplier from volatility overlay
                size_mult = 1.0
                if vol_overlay:
                    try:
                        vol_mult_series = vol_overlay.get_size_multiplier(current_data)
                        if len(vol_mult_series) > 0:
                            size_mult_val = vol_mult_series.iloc[-1]
                            if not pd.isna(size_mult_val) and size_mult_val > 0:
                                size_mult = size_mult_val
                    except Exception:
                        size_mult = 1.0
                
                size_mult *= exposure_mult
                if is_pyramid:
                    size_mult *= self.risk_manager.pyramid_share_scale()
                size_mult = max(size_mult, 0.2)
                
                shares = self.position_sizer.calculate_size(
                    price=current_row['close'],
                    atr=atr,
                    equity=self.risk_manager.equity,
                    size_multiplier=size_mult,
                    stop_mult=stop_mult
                )
                
                if shares <= 0:
                    continue
                
                entry_price = self._apply_costs(current_row['close'], shares, 'entry')
                trade = self.risk_manager.enter_trade(
                    date=date,
                    price=entry_price,
                    signal=signal,
                    atr=atr,
                    shares=shares,
                    strategy=strategy_name,
                    stop_mult=stop_mult,
                    trailing_mult=trailing_mult,
                    is_pyramid=is_pyramid
                )
                if trade and pyramid_threshold is not None:
                    trade.pyramid_trigger = pyramid_threshold
            
            # Update equity curve
            current_equity = self._calculate_current_equity(
                current_row['close'], self.risk_manager.positions
            )
            self.equity_curve.append(current_equity)
            
            # Reset daily tracking
            if i == len(dates) - 1 or dates[i+1].date() != date.date():
                self.risk_manager.reset_daily(date)
        
        # Close any remaining positions
        final_price = df.iloc[-1]['close']
        for trade in self.risk_manager.positions:
            trade.exit_date = dates[-1]
            trade.exit_price = final_price
            trade.exit_reason = "end_of_backtest"
            pnl = trade.calculate_pnl(final_price)
            self.risk_manager.equity += pnl
            self._log_trade(trade, final_price)
        
        # Calculate results
        results = self._calculate_results(df)
        
        return results
    
    def _apply_costs(self, price: float, shares: int, side: str) -> float:
        """Apply trading costs.
        
        Args:
            price: Base price
            shares: Number of shares
            side: 'entry' or 'exit'
        
        Returns:
            Price after costs
        """
        # Commission
        commission = self.commission_per_share * shares
        commission_per_share = commission / shares if shares > 0 else 0
        
        # Slippage
        slippage = price * (self.slippage_bps / 10000.0)
        
        # Market impact
        impact = price * (self.market_impact_bps / 10000.0)
        
        # Total cost per share
        cost_per_share = commission_per_share + slippage + impact
        
        if side == 'entry':
            return price + cost_per_share
        else:
            return price - cost_per_share
    
    def _calculate_current_equity(
        self, current_price: float, positions: List[Trade]
    ) -> float:
        """Calculate current equity including open positions.
        
        Args:
            current_price: Current price
            positions: List of open positions
        
        Returns:
            Current equity
        """
        equity = self.risk_manager.initial_capital
        
        # Add P&L from closed trades
        for trade in self.risk_manager.closed_trades:
            if trade.exit_price:
                pnl = trade.calculate_pnl(trade.exit_price)
                equity += pnl
        
        # Add unrealized P&L from open positions
        for trade in positions:
            pnl = trade.calculate_pnl(current_price)
            equity += pnl
        
        return equity
    
    def _log_trade(self, trade: Trade, current_price: float):
        """Log a closed trade.
        
        Args:
            trade: Trade object
            current_price: Current price (for R multiple calculation)
        """
        if trade.exit_price is None:
            return
        
        risk_per_share = abs(trade.entry_price - trade.stop_price)
        r_multiple = trade.calculate_r_multiple(risk_per_share)
        
        pnl = trade.calculate_pnl(trade.exit_price)
        
        # Apply exit costs
        exit_price_with_costs = self._apply_costs(trade.exit_price, trade.shares, 'exit')
        pnl_with_costs = trade.calculate_pnl(exit_price_with_costs)
        
        self.trade_log.append({
            'entry_date': trade.entry_date,
            'exit_date': trade.exit_date,
            'side': 'long' if trade.signal > 0 else 'short',
            'shares': trade.shares,
            'entry_price': trade.entry_price,
            'exit_price': exit_price_with_costs,
            'stop_price': trade.stop_price,
            'exit_reason': trade.exit_reason,
            'pnl': pnl_with_costs,
            'r_multiple': r_multiple,
            'bars_in_trade': trade.bars_in_trade,
            'strategy': trade.strategy
        })
    
    def _calculate_results(self, df: pd.DataFrame) -> Dict:
        """Calculate backtest results.
        
        Args:
            df: Price DataFrame
        
        Returns:
            Dictionary with results
        """
        if len(self.equity_curve) < 2:
            return {}
        
        equity_series = pd.Series(self.equity_curve[1:], index=df.index[:len(self.equity_curve)-1])
        returns = equity_series.pct_change().dropna()
        
        # Calculate metrics
        total_return = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0]
        
        # CAGR
        years = (equity_series.index[-1] - equity_series.index[0]).days / 365.25
        if years > 0:
            cagr = (equity_series.iloc[-1] / equity_series.iloc[0]) ** (1 / years) - 1
        else:
            cagr = 0.0
        
        # Sharpe ratio
        if returns.std() > 0:
            sharpe = (returns.mean() * 252) / (returns.std() * np.sqrt(252))
        else:
            sharpe = 0.0
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        if downside_returns.std() > 0:
            sortino = (returns.mean() * 252) / (downside_returns.std() * np.sqrt(252))
        else:
            sortino = 0.0
        
        # Drawdown
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        if abs(max_drawdown) > 0:
            calmar = cagr / abs(max_drawdown)
        else:
            calmar = 0.0
        
        # Win rate
        if len(self.trade_log) > 0:
            winning_trades = [t for t in self.trade_log if t['pnl'] > 0]
            win_rate = len(winning_trades) / len(self.trade_log)
        else:
            win_rate = 0.0
        
        # Profit factor
        if len(self.trade_log) > 0:
            gross_profit = sum(t['pnl'] for t in self.trade_log if t['pnl'] > 0)
            gross_loss = abs(sum(t['pnl'] for t in self.trade_log if t['pnl'] < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        else:
            profit_factor = 0.0
        
        # Average R multiple
        if len(self.trade_log) > 0:
            avg_r_multiple = np.mean([t['r_multiple'] for t in self.trade_log])
        else:
            avg_r_multiple = 0.0
        
        # Exposure
        net_exposure, gross_exposure = self.risk_manager.get_exposure()
        
        # Turnover (approximate)
        if len(self.trade_log) > 0:
            total_volume = sum(abs(t['shares'] * t['entry_price']) for t in self.trade_log)
            turnover = total_volume / (equity_series.iloc[0] * len(equity_series))
        else:
            turnover = 0.0
        
        # Best/worst day
        if len(returns) > 0:
            best_day = returns.max()
            worst_day = returns.min()
        else:
            best_day = 0.0
            worst_day = 0.0
        
        # Skewness and kurtosis
        if len(returns) > 0:
            try:
                skew = returns.skew()
            except AttributeError:
                skew = 0.0
            
            try:
                kurtosis = returns.kurtosis()
            except AttributeError:
                # Calculate kurtosis manually if method doesn't exist
                returns_clean = returns.dropna()
                if len(returns_clean) > 3:
                    mean = returns_clean.mean()
                    std = returns_clean.std()
                    if std > 0:
                        normalized = (returns_clean - mean) / std
                        fourth_moment = (normalized ** 4).mean()
                        kurtosis = fourth_moment - 3.0
                    else:
                        kurtosis = 0.0
                else:
                    kurtosis = 0.0
        else:
            skew = 0.0
            kurtosis = 0.0
        
        results = {
            'equity_curve': equity_series,
            'returns': returns,
            'trade_log': self.trade_log,
            'metrics': {
                'cagr': cagr * 100,
                'total_return': total_return * 100,
                'sharpe': sharpe,
                'sortino': sortino,
                'calmar': calmar,
                'max_drawdown': max_drawdown * 100,
                'avg_drawdown': drawdown.mean() * 100,
                'volatility': returns.std() * np.sqrt(252) * 100,
                'win_rate': win_rate * 100,
                'profit_factor': profit_factor,
                'trade_count': len(self.trade_log),
                'avg_r_multiple': avg_r_multiple,
                'net_exposure': net_exposure * 100,
                'gross_exposure': gross_exposure * 100,
                'turnover': turnover,
                'best_day': best_day * 100,
                'worst_day': worst_day * 100,
                'skew': skew,
                'kurtosis': kurtosis
            }
        }
        
        # Save to database if enabled
        if self.save_to_db and self.db:
            try:
                self.backtest_id = self.db.save_backtest(
                    results=results,
                    config_path=None,  # Will be set by CLI
                    config_dict=self.config.model_dump(),
                    start_date=str(df.index[0].date()),
                    end_date=str(df.index[-1].date()),
                    symbol=self.config.symbol.primary,
                    initial_capital=self.config.risk.initial_capital
                )
                results['backtest_id'] = self.backtest_id
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to save backtest to database: {e}")
        
        return results


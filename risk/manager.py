"""Risk management module."""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta


class Trade:
    """Represents a single trade."""
    
    def __init__(
        self,
        entry_date: pd.Timestamp,
        entry_price: float,
        shares: int,
        signal: int,  # 1 for long, -1 for short
        stop_price: float,
        strategy: str = "",
        stop_mult: float = 0.0,
        trailing_mult: float = 0.0,
        is_pyramid: bool = False
    ):
        """Initialize trade."""
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.shares = shares
        self.signal = signal
        self.stop_price = stop_price
        self.trailing_stop = stop_price
        self.stop_mult = stop_mult if stop_mult > 0 else 0.0
        self.trailing_mult = trailing_mult if trailing_mult > 0 else 0.0
        self.initial_stop_price = stop_price
        if signal > 0:
            self.initial_risk_per_share = max(entry_price - stop_price, 1e-6)
        else:
            self.initial_risk_per_share = max(stop_price - entry_price, 1e-6)
        self.current_r_multiple = 0.0
        self.is_pyramid = is_pyramid
        self.exit_date: Optional[pd.Timestamp] = None
        self.exit_price: Optional[float] = None
        self.exit_reason: str = ""
        self.strategy = strategy
        self.bars_in_trade = 0
        self.max_adverse_excursion = 0.0
        self.max_favorable_excursion = 0.0
    
    def update_trailing_stop(
        self, current_price: float, atr: float, default_trailing_mult: float = 1.5
    ):
        """Update trailing stop using the trade's trailing multiplier if supplied."""
        trailing_mult = self.trailing_mult if self.trailing_mult > 0 else default_trailing_mult
        trailing_distance = atr * trailing_mult
        
        if self.signal > 0:  # Long
            new_stop = current_price - trailing_distance
            self.trailing_stop = max(self.trailing_stop, new_stop)
        else:  # Short
            new_stop = current_price + trailing_distance
            self.trailing_stop = min(self.trailing_stop, new_stop)
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate current P&L.
        
        Args:
            current_price: Current price
        
        Returns:
            P&L in dollars
        """
        if self.signal > 0:  # Long
            pnl = (current_price - self.entry_price) * self.shares
        else:  # Short
            pnl = (self.entry_price - current_price) * self.shares
        return pnl
    
    def calculate_r_multiple(self, risk_per_share: float) -> float:
        """Calculate R multiple.
        
        Args:
            risk_per_share: Risk per share (entry - stop for long)
        
        Returns:
            R multiple
        """
        if self.exit_price is None or risk_per_share == 0:
            return 0.0
        
        if self.signal > 0:  # Long
            return_amount = (self.exit_price - self.entry_price) * self.shares
            risk_amount = abs(self.entry_price - self.stop_price) * self.shares
        else:  # Short
            return_amount = (self.entry_price - self.exit_price) * self.shares
            risk_amount = abs(self.stop_price - self.entry_price) * self.shares
        
        if risk_amount > 0:
            return return_amount / risk_amount
        return 0.0


class RiskManager:
    """Manages risk and positions."""
    
    def __init__(self, config: Dict):
        """Initialize risk manager.
        
        Args:
            config: Risk configuration dictionary
        """
        self.config = config
        self.initial_capital = config.get('initial_capital', 100000)
        self.equity = self.initial_capital
        self.peak_equity = self.initial_capital
        
        # Risk limits
        self.per_trade_risk_pct = config.get('per_trade_risk_pct', 1.0)
        self.max_net_exposure = config.get('max_net_exposure', 1.5)
        self.min_net_exposure = config.get('min_net_exposure', -1.0)
        self.max_gross_exposure = config.get('max_gross_exposure', 2.0)
        self.stop_atr_mult = config.get('stop_atr_mult', 2.5)
        self.trailing_stop_atr_mult = config.get('trailing_stop_atr_mult', 1.5)
        self.trailing_start_r = config.get('trailing_start_r', 1.0)
        self.trailing_mid_r = config.get('trailing_mid_r', 2.0)
        self.trailing_end_r = config.get('trailing_end_r', 4.0)
        self.trailing_start_mult = config.get('trailing_start_mult', 1.5)
        self.trailing_mid_mult = config.get('trailing_mid_mult', 1.0)
        self.trailing_end_mult = config.get('trailing_end_mult', 0.8)
        self.time_stop_bars = config.get('time_stop_bars', 20)
        self.daily_loss_limit_pct = config.get('daily_loss_limit_pct', 2.5)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 18.0)
        self.drawdown_recovery_exposure = config.get('drawdown_recovery_exposure', 0.4)
        self.pyramid_enabled = config.get('pyramid_enabled', False)
        self.pyramid_max_adds = config.get('pyramid_max_adds', 0)
        self.pyramid_add_thresholds = config.get('pyramid_add_thresholds', [])
        self.pyramid_add_scale = config.get('pyramid_add_scale', 0.5)
        
        # State
        self.positions: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.daily_pnl = 0.0
        self.last_trade_date: Optional[pd.Timestamp] = None
        self.trading_paused = False
        
        # Daily tracking
        self.daily_equity = [self.initial_capital]
        self.daily_dates = [datetime.now()]
    
    def can_enter_trade(self, signal: int, price: float, atr: float) -> bool:
        """Check if we can enter a new trade.
        
        Args:
            signal: Signal direction (1 = long, -1 = short)
            price: Entry price
            atr: ATR value
        
        Returns:
            True if trade can be entered
        """
        # Check if trading is paused
        if self.trading_paused:
            return False
        
        # Check drawdown limits
        current_dd = self.get_current_drawdown()
        if current_dd > self.max_drawdown_pct:
            return False
        
        # Check exposure limits
        net_exposure, gross_exposure = self.get_exposure()
        
        if signal > 0:
            if net_exposure >= self.max_net_exposure:
                return False
        else:
            if net_exposure <= self.min_net_exposure:
                return False
        
        if gross_exposure >= self.max_gross_exposure:
            return False
        
        # Check daily loss limit
        if self.daily_pnl < -(self.equity * self.daily_loss_limit_pct / 100.0):
            return False
        
        return True
    
    def enter_trade(
        self,
        date: pd.Timestamp,
        price: float,
        signal: int,
        atr: float,
        shares: int,
        strategy: str = "",
        stop_mult: Optional[float] = None,
        trailing_mult: Optional[float] = None,
        is_pyramid: bool = False
    ) -> Optional[Trade]:
        """Enter a new trade with optional dynamic stop settings."""
        if not self.can_enter_trade(signal, price, atr):
            return None
        
        stop_multiplier = stop_mult if stop_mult is not None else self.stop_atr_mult
        trailing_multiplier = trailing_mult if trailing_mult is not None else self.trailing_stop_atr_mult
        
        stop_price = self.calculate_stop_price(price, atr, signal, stop_multiplier)
        
        trade = Trade(
            entry_date=date,
            entry_price=price,
            shares=shares,
            signal=signal,
            stop_price=stop_price,
            strategy=strategy,
            stop_mult=stop_multiplier,
            trailing_mult=trailing_multiplier,
            is_pyramid=is_pyramid
        )
        
        self.positions.append(trade)
        self.last_trade_date = date
        
        return trade
    
    def force_exit(self, trade: Trade, date: pd.Timestamp, price: float, reason: str) -> None:
        trade.exit_date = date
        trade.exit_price = price
        trade.exit_reason = reason
        pnl = trade.calculate_pnl(price)
        self.equity += pnl
        self.daily_pnl += pnl
        if trade in self.positions:
            self.positions.remove(trade)
        self.closed_trades.append(trade)
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def update_positions(
        self,
        date: pd.Timestamp,
        current_price: float,
        atr: float,
        high: float,
        low: float
    ) -> List[Trade]:
        """Update positions and check for exits."""
        closed_trades = []
        
        for trade in self.positions[:]:  # Copy list to modify during iteration
            trade.bars_in_trade += 1
            
            # Compute R multiple based on initial risk per share
            if trade.signal > 0:
                gain_per_share = current_price - trade.entry_price
            else:
                gain_per_share = trade.entry_price - current_price
            initial_risk = trade.initial_risk_per_share if trade.initial_risk_per_share > 0 else max(abs(trade.entry_price - trade.initial_stop_price), 1e-6)
            r_multiple = gain_per_share / initial_risk if initial_risk > 0 else 0.0
            trade.current_r_multiple = r_multiple
            
            # Update trailing stop only when trade is sufficiently in profit
            if r_multiple >= self.trailing_end_r:
                trade.trailing_mult = max(self.trailing_end_mult, 0.1)
                trade.update_trailing_stop(current_price, atr, self.trailing_stop_atr_mult)
            elif r_multiple >= self.trailing_mid_r:
                trade.trailing_mult = max(self.trailing_mid_mult, 0.1)
                trade.update_trailing_stop(current_price, atr, self.trailing_stop_atr_mult)
            elif r_multiple >= self.trailing_start_r:
                trade.trailing_mult = max(self.trailing_start_mult, 0.1)
                trade.update_trailing_stop(current_price, atr, self.trailing_stop_atr_mult)
            
            # Update excursions
            pnl = trade.calculate_pnl(current_price)
            pnl_pct = pnl / (trade.entry_price * trade.shares) * 100
            
            if pnl < trade.max_adverse_excursion:
                trade.max_adverse_excursion = pnl
            if pnl > trade.max_favorable_excursion:
                trade.max_favorable_excursion = pnl
            
            # Stop loss
            exit_reason = None
            exit_price = current_price
            if trade.signal > 0:
                if low <= trade.trailing_stop:
                    exit_reason = "stop_loss"
                    exit_price = trade.trailing_stop
            else:
                if high >= trade.trailing_stop:
                    exit_reason = "stop_loss"
                    exit_price = trade.trailing_stop
            
            # Time stop
            if not exit_reason and self.time_stop_bars > 0 and trade.bars_in_trade >= self.time_stop_bars and pnl <= 0:
                exit_reason = "time_stop"
            
            if exit_reason:
                self.force_exit(trade, date, exit_price, exit_reason)
                closed_trades.append(trade)
        
        return closed_trades
    
    def calculate_stop_price(self, entry_price: float, atr: float, signal: int, stop_mult: Optional[float] = None) -> float:
        """Calculate stop price."""
        effective_mult = stop_mult if stop_mult is not None else self.stop_atr_mult
        stop_distance = atr * effective_mult
        
        if signal > 0:  # Long
            return entry_price - stop_distance
        else:  # Short
            return entry_price + stop_distance
    
    def get_exposure(self) -> tuple[float, float]:
        """Get current exposure."""
        long_value = sum(
            p.entry_price * p.shares for p in self.positions if p.signal > 0
        )
        short_value = sum(
            p.entry_price * p.shares for p in self.positions if p.signal < 0
        )

        net_exposure = (long_value - short_value) / self.equity if self.equity > 0 else 0
        gross_exposure = (long_value + short_value) / self.equity if self.equity > 0 else 0

        return net_exposure, gross_exposure
    
    def get_current_drawdown(self) -> float:
        """Get current drawdown as percentage.
        
        Returns:
            Drawdown percentage
        """
        if self.peak_equity > 0:
            return (self.equity - self.peak_equity) / self.peak_equity * 100
        return 0.0
    
    def reset_daily(self, date: pd.Timestamp):
        """Reset daily tracking.
        
        Args:
            date: Current date
        """
        self.daily_pnl = 0.0
        self.daily_equity.append(self.equity)
        self.daily_dates.append(date)
        
        # Check if we should pause trading due to daily loss
        if self.daily_pnl < -(self.equity * self.daily_loss_limit_pct / 100.0):
            self.trading_paused = True
        else:
            self.trading_paused = False
        
        # Check drawdown recovery
        current_dd = self.get_current_drawdown()
        if current_dd > self.max_drawdown_pct:
            # Reduce exposure
            self.per_trade_risk_pct *= self.drawdown_recovery_exposure
    
    def can_pyramid(self, signal: int, strategy_name: str) -> Optional[tuple[Trade, float]]:
        if not self.pyramid_enabled:
            return None
        same_trades = [t for t in self.positions if t.signal == signal and t.strategy == strategy_name]
        if not same_trades:
            return None
        base_trade = same_trades[0]
        add_count = len(same_trades) - 1
        if add_count >= self.pyramid_max_adds:
            return None
        thresholds = self.pyramid_add_thresholds or []
        if thresholds:
            threshold = thresholds[min(add_count, len(thresholds) - 1)]
        else:
            threshold = 1.5 * (add_count + 1)
        if base_trade.current_r_multiple >= threshold:
            return (base_trade, threshold)
        return None
    
    def pyramid_share_scale(self) -> float:
        return max(self.pyramid_add_scale, 0.1)


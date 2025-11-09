"""Position sizing module."""

import pandas as pd
import numpy as np
from typing import Optional


class PositionSizer:
    """Calculates position sizes based on risk parameters."""
    
    def __init__(
        self,
        initial_capital: float = 100000,
        per_trade_risk_pct: float = 1.0,
        stop_atr_mult: float = 2.5
    ):
        """Initialize position sizer.
        
        Args:
            initial_capital: Initial capital
            per_trade_risk_pct: Risk per trade as % of equity
            stop_atr_mult: Stop distance in ATR multiples
        """
        self.initial_capital = initial_capital
        self.per_trade_risk_pct = per_trade_risk_pct
        self.stop_atr_mult = stop_atr_mult
    
    def calculate_size(
        self,
        price: float,
        atr: float,
        equity: float,
        size_multiplier: float = 1.0,
        stop_mult: Optional[float] = None
    ) -> float:
        """Calculate position size based on risk.
        
        Args:
            price: Entry price
            atr: ATR value
            equity: Current equity
            size_multiplier: Additional size multiplier (from vol overlay, etc.)
            stop_mult: Optional override for stop ATR multiple
        
        Returns:
            Number of shares to trade
        """
        # Risk per trade
        risk_amount = equity * (self.per_trade_risk_pct / 100.0)
        
        # Stop distance (allow dynamic overrides)
        effective_stop_mult = stop_mult if stop_mult is not None else self.stop_atr_mult
        stop_distance = atr * effective_stop_mult
        
        # Position size
        if stop_distance > 0:
            shares = (risk_amount / stop_distance) * size_multiplier
        else:
            shares = 0.0
        
        return max(0, int(shares))
    
    def calculate_stop_price(
        self,
        entry_price: float,
        atr: float,
        signal: int  # 1 for long, -1 for short
    ) -> float:
        """Calculate stop price.
        
        Args:
            entry_price: Entry price
            atr: ATR value
            signal: Signal direction (1 = long, -1 = short)
        
        Returns:
            Stop price
        """
        stop_distance = atr * self.stop_atr_mult
        
        if signal > 0:  # Long
            stop_price = entry_price - stop_distance
        else:  # Short
            stop_price = entry_price + stop_distance
        
        return stop_price


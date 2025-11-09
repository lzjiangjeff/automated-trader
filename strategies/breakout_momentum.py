"""Breakout-Momentum strategy implementation."""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy


class BreakoutMomentumStrategy(BaseStrategy):
    """Breakout momentum strategy with volume and ADX confirmation."""
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Generate signals based on breakouts with confirmation.
        
        Long: New high breakout with RVOL > threshold and ADX > threshold
        Short: New low breakdown with RVOL > threshold and ADX > threshold
        """
        self.validate_data(df)
        
        signals = pd.Series(0, index=df.index, name='signal')
        
        lookback = self.config.get('lookback', 22)
        rvol_threshold = self.config.get('rvol_threshold', 1.4)
        adx_threshold = self.config.get('adx_threshold', 18.0)
        atr_buffer_mult = self.config.get('atr_buffer_mult', 0.25)
        long_only = self.config.get('long_only', False)
        
        # Check required indicators
        required_cols = ['rvol', 'adx', 'atr']
        if not all(col in df.columns for col in required_cols):
            return signals.to_frame()
        
        # Calculate rolling highs and lows
        rolling_high = df['high'].rolling(window=lookback).max()
        rolling_low = df['low'].rolling(window=lookback).min()
        
        # ATR buffer to avoid whipsaws
        atr_buffer = df['atr'] * atr_buffer_mult
        
        # Breakout conditions
        high_breakout = df['close'] > (rolling_high.shift(1) + atr_buffer)
        low_breakdown = df['close'] < (rolling_low.shift(1) - atr_buffer)
        
        # Confirmation filters
        volume_confirm = df['rvol'] > rvol_threshold
        adx_confirm = df['adx'] > adx_threshold
        
        # Generate signals
        long_condition = high_breakout & volume_confirm & adx_confirm
        short_condition = low_breakdown & volume_confirm & adx_confirm
        if long_only:
            short_condition = pd.Series(False, index=df.index)
        
        signals[long_condition] = 1
        signals[short_condition] = -1
        
        return signals.to_frame()


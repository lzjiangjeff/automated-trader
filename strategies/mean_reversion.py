"""Mean-Reversion strategy implementation."""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """Mean-reversion strategy that fades extreme moves."""
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Generate signals based on mean reversion.
        
        Long: Price below mean - std_dev * multiplier when ADX < threshold (non-trending)
        Short: Price above mean + std_dev * multiplier when ADX < threshold (non-trending)
        Only active when volatility is compressing (BB width in lower quantile)
        """
        self.validate_data(df)
        
        signals = pd.Series(0, index=df.index, name='signal')
        
        lookback = self.config.get('lookback', 20)
        std_dev = self.config.get('std_dev', 2.5)
        adx_threshold = self.config.get('adx_threshold', 18)
        bb_width_quantile = self.config.get('bb_width_quantile', 0.3)
        
        # Check required indicators
        required_cols = ['adx', 'bb_width', 'bb_lower', 'bb_upper', 'bb_middle']
        if not all(col in df.columns for col in required_cols):
            return signals.to_frame()
        
        # Calculate mean and standard deviation
        mean = df['close'].rolling(window=lookback).mean()
        std = df['close'].rolling(window=lookback).std()
        
        # Non-trending regime (low ADX)
        non_trending = df['adx'] < adx_threshold
        
        # Volatility compression (BB width in lower quantile)
        bb_width_threshold = df['bb_width'].rolling(window=50).quantile(bb_width_quantile)
        vol_compressing = df['bb_width'] < bb_width_threshold
        
        # Mean reversion conditions
        price_below_mean = df['close'] < (mean - std * std_dev)
        price_above_mean = df['close'] > (mean + std * std_dev)
        
        # Alternative: Use Bollinger Bands
        price_near_lower_bb = df['close'] <= df['bb_lower']
        price_near_upper_bb = df['close'] >= df['bb_upper']
        
        # Generate signals (fade extremes)
        long_condition = (
            non_trending & 
            vol_compressing & 
            (price_below_mean | price_near_lower_bb)
        )
        short_condition = (
            non_trending & 
            vol_compressing & 
            (price_above_mean | price_near_upper_bb)
        )
        
        signals[long_condition] = 1
        signals[short_condition] = -1
        
        return signals.to_frame()


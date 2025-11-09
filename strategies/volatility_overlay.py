"""Volatility Overlay strategy for position sizing."""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy


class VolatilityOverlayStrategy(BaseStrategy):
    """Volatility-based position sizing overlay."""
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Generate position sizing multipliers based on volatility.
        
        This is an overlay strategy that modifies position sizes rather than
        generating directional signals. Returns neutral signals (0) but provides
        size multipliers via get_size_multiplier method.
        """
        self.validate_data(df)
        
        signals = pd.Series(0, index=df.index, name='signal')
        return signals.to_frame()
    
    def get_size_multiplier(self, df: pd.DataFrame) -> pd.Series:
        """Get position size multiplier based on ATR percentile.
        
        Args:
            df: DataFrame with features
        
        Returns:
            Series of size multipliers
        """
        atr_period = self.config.get('atr_period', 14)
        vol_target_annual = self.config.get('vol_target_annual', 0.25)
        min_size_mult = self.config.get('min_size_mult', 0.5)
        max_size_mult = self.config.get('max_size_mult', 1.5)
        
        if 'atr' not in df.columns:
            return pd.Series(1.0, index=df.index)
        
        atr = df['atr'].rolling(window=max(atr_period, 10)).mean()
        atr_percentile = atr.rolling(window=50).rank(pct=True)
        size_mult = 1.0 / (1.0 + atr_percentile)
        size_mult = size_mult * (max_size_mult - min_size_mult) + min_size_mult
        
        if 'returns' in df.columns:
            realized_vol = df['returns'].rolling(window=20).std() * np.sqrt(252)
            vol_adjustment = vol_target_annual / (realized_vol + 0.01)
            vol_adjustment = np.clip(vol_adjustment, 0.5, 2.0)
            size_mult = size_mult * vol_adjustment
        
        size_mult = np.clip(size_mult, min_size_mult, max_size_mult)
        
        return pd.Series(size_mult, index=df.index).fillna(1.0)


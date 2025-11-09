"""Ensemble strategy that combines multiple strategies."""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from strategies.base import BaseStrategy
from strategies.trend_ema import TrendEMAStrategy
from strategies.breakout_momentum import BreakoutMomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy


class EnsembleStrategy(BaseStrategy):
    """Ensemble strategy that weights multiple strategies."""
    
    def __init__(self, config: Dict, strategies: Optional[List[BaseStrategy]] = None):
        """Initialize ensemble strategy.
        
        Args:
            config: Ensemble configuration
            strategies: List of strategy instances to ensemble
        """
        super().__init__(config)
        self.strategies = strategies or []
        self.weights = config.get('weights', {})
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Generate weighted ensemble signals.
        
        Args:
            df: Primary symbol DataFrame
            context: Context DataFrames
        
        Returns:
            DataFrame with weighted signal
        """
        if not self.strategies:
            return pd.Series(0, index=df.index, name='signal').to_frame()
        
        # Get signals from each strategy
        strategy_signals = {}
        total_weight = 0.0
        
        for strategy in self.strategies:
            # Skip strategies that don't generate signals (overlays/filters)
            # These are: VolatilityOverlayStrategy, RegimeFilterStrategy
            if 'Overlay' in strategy.name or 'Filter' in strategy.name:
                continue
            
            strategy_name = strategy.name.replace('Strategy', '').lower()
            weight = self.weights.get(strategy_name, 0.0)
            
            if weight > 0:
                try:
                    signals_df = strategy.generate_signals(df, context)
                    if 'signal' in signals_df.columns and len(signals_df) > 0:
                        strategy_signals[strategy_name] = signals_df['signal'] * weight
                        total_weight += weight
                except Exception:
                    # Skip strategies that fail to generate signals
                    continue
        
        if not strategy_signals:
            return pd.Series(0, index=df.index, name='signal').to_frame()
        
        # Normalize weights
        if total_weight > 0:
            for strategy_name in strategy_signals:
                strategy_signals[strategy_name] = strategy_signals[strategy_name] / total_weight
        
        # Combine signals
        combined_signals = pd.DataFrame(strategy_signals)
        ensemble_signal = combined_signals.sum(axis=1)
        
        # Convert to discrete signals
        # Use a lower threshold to be more sensitive to signals
        # Threshold of 0.2 means we need at least 20% weighted consensus
        threshold = 0.2
        discrete_signal = pd.Series(0, index=df.index)
        
        # Check if we have any non-zero signals
        if len(ensemble_signal) > 0:
            discrete_signal[ensemble_signal > threshold] = 1
            discrete_signal[ensemble_signal < -threshold] = -1
        else:
            # If no signals, return all zeros
            pass
        
        return discrete_signal.to_frame(name='signal')


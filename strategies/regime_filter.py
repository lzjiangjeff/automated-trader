"""Regime Filter strategy for market regime detection."""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy


class RegimeFilterStrategy(BaseStrategy):
    """Regime filter based on QQQ trend and VIX levels."""
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Generate regime signals.
        
        Risk-on: QQQ above SMA200 and VIX < threshold -> allow full exposure
        Risk-off: Otherwise -> reduce exposure or flip to short-only
        """
        self.validate_data(df)
        
        signals = pd.Series(0, index=df.index, name='signal')
        
        qqq_sma_period = self.config.get('qqq_sma_period', 200)
        vix_threshold = self.config.get('vix_threshold', 25)
        risk_off_exposure = self.config.get('risk_off_exposure', 0.25)
        
        # Check if we have context data
        if context is None:
            return signals.to_frame()
        
        qqq_df = context.get('QQQ')
        vix_df = context.get('VIX')
        
        if qqq_df is None or vix_df is None:
            return signals.to_frame()
        
        # Align indices
        common_dates = df.index.intersection(qqq_df.index).intersection(vix_df.index)
        if len(common_dates) == 0:
            return signals.to_frame()
        
        # QQQ trend
        if f'sma_{qqq_sma_period}' in qqq_df.columns:
            qqq_above_sma = qqq_df.loc[common_dates, 'close'] > qqq_df.loc[common_dates, f'sma_{qqq_sma_period}']
        else:
            qqq_sma = qqq_df.loc[common_dates, 'close'].rolling(window=qqq_sma_period).mean()
            qqq_above_sma = qqq_df.loc[common_dates, 'close'] > qqq_sma
        
        # VIX level
        vix_close = vix_df.loc[common_dates, 'close']
        vix_low = vix_close < vix_threshold
        
        # Risk-on regime
        risk_on = qqq_above_sma & vix_low
        
        # In risk-on: allow signals to pass through (return 0, handled by exposure multiplier)
        # In risk-off: reduce exposure (handled by exposure multiplier, not signal generation)
        
        # For extreme risk-off, we could generate short signals
        # For now, we'll use exposure multiplier in risk management
        
        return signals.to_frame()
    
    def get_exposure_multiplier(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.Series:
        """Get exposure multiplier based on regime.
        
        Args:
            df: Primary symbol DataFrame
            context: Context DataFrames
        
        Returns:
            Series of exposure multipliers (1.0 = full, 0.25 = reduced)
        """
        multipliers = pd.Series(1.0, index=df.index)
        
        qqq_sma_period = self.config.get('qqq_sma_period', 200)
        vix_threshold = self.config.get('vix_threshold', 25)
        risk_off_exposure = self.config.get('risk_off_exposure', 0.25)
        
        if context is None:
            return multipliers
        
        qqq_df = context.get('QQQ')
        vix_df = context.get('VIX')
        
        if qqq_df is None or vix_df is None:
            return multipliers
        
        # Align indices
        common_dates = df.index.intersection(qqq_df.index).intersection(vix_df.index)
        if len(common_dates) == 0:
            return multipliers
        
        # QQQ trend
        if f'sma_{qqq_sma_period}' in qqq_df.columns:
            qqq_above_sma = qqq_df.loc[common_dates, 'close'] > qqq_df.loc[common_dates, f'sma_{qqq_sma_period}']
        else:
            qqq_sma = qqq_df.loc[common_dates, 'close'].rolling(window=qqq_sma_period).mean()
            qqq_above_sma = qqq_df.loc[common_dates, 'close'] > qqq_sma
        
        # VIX level
        vix_close = vix_df.loc[common_dates, 'close']
        vix_low = vix_close < vix_threshold
        
        # Risk-on regime
        risk_on = qqq_above_sma & vix_low
        
        # Set multipliers using boolean indexing
        # For risk_on dates: set to 1.0, for risk_off dates: set to risk_off_exposure
        # risk_on is a Series with index common_dates
        # Use replace to map True->1.0 and False->risk_off_exposure
        exposure_values = risk_on.replace({True: 1.0, False: risk_off_exposure})
        multipliers.loc[common_dates] = exposure_values
        
        # Forward fill for dates not in common_dates
        multipliers = multipliers.ffill().fillna(1.0)
        
        return multipliers


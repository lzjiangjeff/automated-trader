"""Trend-EMA strategy implementation."""

import pandas as pd
from typing import Dict, Optional
from strategies.base import BaseStrategy


class TrendEMAStrategy(BaseStrategy):
    """Momentum trend strategy that rides strong bullish regimes."""
    
    def generate_signals(
        self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """Go long on fresh bullish crossovers above higher timeframe trend."""
        self.validate_data(df)
        signals = pd.Series(0, index=df.index, name='signal')
        
        config = self.config
        ema_fast = config.get('ema_fast', 12)
        ema_medium = config.get('ema_medium', 26)
        ema_slow = config.get('ema_slow', 55)
        rsi_threshold = config.get('rsi_long_threshold', 0)
        long_only = config.get('long_only', True)
        regime_enabled = config.get('regime_filter_enabled', True)
        regime_period = config.get('regime_sma_period', 250)
        dual_tf_enabled = config.get('dual_timeframe_enabled', True)
        dual_tf_ema = config.get('dual_timeframe_ema', 144)
        pullback_tolerance = config.get('pullback_tolerance', 0.04)
        continuation_tolerance = config.get('continuation_tolerance', 0.03)
        max_volatility = config.get('max_volatility', 0.45)
        cooldown = max(1, config.get('min_bars_between_signals', 1))
        exit_buffer = config.get('exit_buffer', 0.01)
        fast_buffer = config.get('fast_buffer', 0.0)
        vol_stop_bars = config.get('volatility_time_stop_bars', 0)
        vol_stop_threshold = config.get('volatility_time_stop_threshold', 0.0)
        adx_threshold = config.get('adx_threshold', 0)

        ema_fast_col = f'ema_{ema_fast}'
        ema_medium_col = f'ema_{ema_medium}'
        ema_slow_col = f'ema_{ema_slow}'
        sma50_col = 'sma_50'
        sma200_col = 'sma_200'
        dual_ema_col = f'ema_{dual_tf_ema}'
        required_cols = [ema_fast_col, ema_medium_col, ema_slow_col, sma50_col, sma200_col]
        if dual_tf_enabled:
            required_cols.append(dual_ema_col)
        if not all(col in df.columns for col in required_cols):
            return signals.to_frame()

        # Momentum triggers
        rolling_high = df['high'].rolling(window=20, min_periods=1).max()
        cross_fast = (
            (df['close'] > df[ema_fast_col]) &
            (df['close'].shift(1) <= df[ema_fast_col].shift(1))
        )
        cross_medium = (
            (df['close'] > df[ema_medium_col]) &
            (df['close'].shift(1) <= df[ema_medium_col].shift(1))
        )
        swing_break = df['close'] > rolling_high.shift(1)

        # Core bullish regime
        bullish_trend = (
            (df[ema_fast_col] > df[ema_medium_col]) &
            (df[ema_medium_col] > df[ema_slow_col]) &
            (df['close'] > df[ema_slow_col])
        )
        bullish_trend = bullish_trend.fillna(False)

        # Regime filter
        regime_condition = pd.Series(True, index=df.index)
        if regime_enabled:
            regime_col = f'sma_{regime_period}'
            if regime_col not in df.columns:
                df[regime_col] = df['close'].rolling(regime_period).mean()
            regime_condition = (df['close'] > df[regime_col]).fillna(False)

        # Dual timeframe filter
        dual_condition = pd.Series(True, index=df.index)
        if dual_tf_enabled and dual_ema_col in df.columns:
            dual_condition = (df['close'] > df[dual_ema_col]).fillna(False)

        # RSI confirmation (optional)
        rsi_ok = pd.Series(True, index=df.index)
        if rsi_threshold and 'rsi' in df.columns:
            rsi_ok = (df['rsi'] > rsi_threshold).fillna(False)

        # ADX confirmation
        adx_ok = pd.Series(True, index=df.index)
        if adx_threshold and 'adx' in df.columns:
            adx_ok = (df['adx'] > adx_threshold).fillna(False)

        # Volatility filter using ATR/price
        vol_ok = pd.Series(True, index=df.index)
        effective_max_vol = max_volatility if max_volatility and max_volatility > 0 else None
        if effective_max_vol:
            atr_series = df.get('atr')
            if atr_series is not None:
                volatility = (atr_series / df['close']).fillna(method='ffill')
                vol_ok = (volatility < effective_max_vol).fillna(True)

        # Combine filters for long entries
        trigger = (cross_medium | swing_break) & (df['close'] > df[ema_fast_col] * (1 + fast_buffer))
        raw_long = (
            trigger &
            bullish_trend &
            regime_condition &
            dual_condition &
            rsi_ok &
            adx_ok &
            vol_ok
        ).fillna(False)
        
        # Cooldown
        if cooldown > 1 and raw_long.any():
            last_entry = None
            for idx in raw_long[raw_long].index:
                if last_entry is None or (idx - last_entry).days >= cooldown:
                    signals.at[idx] = 1
                    last_entry = idx
        else:
            signals.loc[raw_long] = 1
        
        # Optional shorts (unused for long-only configs)
        if not long_only:
            bearish_trend = (
                (df[ema_fast_col] < df[ema_medium_col]) &
                (df[ema_medium_col] < df[ema_slow_col]) &
                (df['close'] < df[sma50_col]) &
                (df[sma50_col] < df[sma200_col])
            ).fillna(False)
            fresh_short = bearish_trend & (~bearish_trend.shift(1).fillna(False))
            dual_short = (~dual_condition) if dual_tf_enabled else True
            raw_short = (fresh_short & (~regime_condition) & dual_short & vol_ok).fillna(False)
            if cooldown > 1 and raw_short.any():
                last_entry = None
                for idx in raw_short[raw_short].index:
                    if last_entry is None or (idx - last_entry).days >= cooldown:
                        signals.at[idx] = -1
                        last_entry = idx
            else:
                signals.loc[raw_short] = -1
        
        self._ema_fast_col = ema_fast_col
        self._ema_medium_col = ema_medium_col
        self._ema_slow_col = ema_slow_col
        self._exit_buffer = exit_buffer
        self._long_only = long_only
        return signals.to_frame()

    def should_exit(self, df: pd.DataFrame) -> bool:
        if len(df) == 0:
            return False
        if not hasattr(self, '_ema_fast_col'):
            return False
        row = df.iloc[-1]
        ema_fast = row.get(self._ema_fast_col)
        ema_medium = row.get(self._ema_medium_col)
        ema_slow = row.get(self._ema_slow_col)
        close = row.get('close')
        if pd.isna(ema_fast) or pd.isna(ema_medium) or pd.isna(ema_slow) or pd.isna(close):
            return False
        medium_break = ema_fast <= ema_medium and close <= ema_medium
        if medium_break:
            return True
        buffer = 1.0 - self._exit_buffer if hasattr(self, '_exit_buffer') else 0.98
        if close <= ema_slow * buffer:
            return True
        vol_stop_bars = getattr(self, '_vol_stop_bars', 0)
        vol_stop_threshold = getattr(self, '_vol_stop_threshold', 0.0)
        if vol_stop_bars > 0 and 'atr' in df.columns:
            recent = df.iloc[-vol_stop_bars:]
            if len(recent) == vol_stop_bars:
                vol_ratio = (recent['atr'] / recent['close']).dropna()
                if len(vol_ratio) == vol_stop_bars and (vol_ratio < vol_stop_threshold).all():
                    return True
        return False


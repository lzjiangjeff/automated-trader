"""Feature engineering for trading strategies."""

import pandas as pd
import numpy as np
from typing import Optional
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("Warning: TA-Lib not available. Some indicators may be unavailable.")


class FeatureEngineer:
    """Engineers technical indicators and features."""
    
    def __init__(self, use_talib: bool = True):
        """Initialize feature engineer.
        
        Args:
            use_talib: Whether to use TA-Lib for indicators
        """
        self.use_talib = use_talib and TALIB_AVAILABLE
    
    def calculate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all features for a DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            DataFrame with added features
        """
        df = df.copy()
        
        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Basic features
        df = self._add_basic_features(df)
        
        # Moving averages
        df = self._add_moving_averages(df)
        
        # Momentum indicators
        df = self._add_momentum_indicators(df)
        
        # Volatility indicators
        df = self._add_volatility_indicators(df)
        
        # Volume indicators
        df = self._add_volume_indicators(df)
        
        # Statistical features
        df = self._add_statistical_features(df)
        
        # Regime indicators
        df = self._add_regime_indicators(df)
        
        return df
    
    def _add_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add basic price features."""
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['gap_pct'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1) * 100
        df['high_low_pct'] = (df['high'] - df['low']) / df['close'] * 100
        return df
    
    def _add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add moving averages."""
        # EMAs
        ema_periods = [5, 8, 12, 21, 26, 34, 50, 55, 89, 144, 200]
        for period in ema_periods:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        # SMAs
        sma_periods = [20, 50, 100, 150, 200]
        for period in sma_periods:
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        
        return df
    
    def _add_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum indicators."""
        if self.use_talib:
            # RSI
            df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
            
            # MACD
            macd, macdsignal, macdhist = talib.MACD(
                df['close'].values, fastperiod=12, slowperiod=26, signalperiod=9
            )
            df['macd'] = macd
            df['macd_signal'] = macdsignal
            df['macd_hist'] = macdhist
            
            # ADX
            df['adx'] = talib.ADX(
                df['high'].values, df['low'].values, df['close'].values, timeperiod=14
            )
        else:
            # Fallback implementations
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            df['macd'], df['macd_signal'], df['macd_hist'] = self._calculate_macd(df['close'])
            df['adx'] = self._calculate_adx(df['high'], df['low'], df['close'], 14)
        
        return df
    
    def _add_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility indicators."""
        # ATR
        if self.use_talib:
            df['atr'] = talib.ATR(
                df['high'].values, df['low'].values, df['close'].values, timeperiod=14
            )
        else:
            df['atr'] = self._calculate_atr(df['high'], df['low'], df['close'], 14)
        
        # Bollinger Bands
        if self.use_talib:
            upper, middle, lower = talib.BBANDS(
                df['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
            )
            df['bb_upper'] = upper
            df['bb_middle'] = middle
            df['bb_lower'] = lower
        else:
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * std
            df['bb_lower'] = df['bb_middle'] - 2 * std
        
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Realized volatility
        df['realized_vol'] = df['returns'].rolling(window=20).std() * np.sqrt(252)
        
        # Volatility regime
        df['vol_regime_high'] = (df['atr'] > df['atr'].rolling(window=50).quantile(0.75)).astype(int)
        df['vol_regime_low'] = (df['atr'] < df['atr'].rolling(window=50).quantile(0.25)).astype(int)
        
        return df
    
    def _add_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume indicators."""
        # Relative volume
        df['rvol'] = df['volume'] / df['volume'].rolling(window=20).mean()
        
        return df
    
    def _add_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add statistical features."""
        # Rolling skewness - use apply for compatibility
        try:
            df['skew_20'] = df['returns'].rolling(window=20).skew()
        except AttributeError:
            # Fallback if skew() is not available
            df['skew_20'] = df['returns'].rolling(window=20).apply(
                lambda x: x.skew() if len(x.dropna()) > 2 else np.nan,
                raw=False
            )
        
        # Rolling kurtosis - calculate using apply since kurtosis() method may not exist
        def calc_kurtosis(x):
            """Calculate kurtosis for a rolling window."""
            # Convert to numpy array for easier calculation
            x_arr = np.array(x.dropna(), dtype=float)
            if len(x_arr) < 4:
                return np.nan
            mean = np.mean(x_arr)
            std = np.std(x_arr, ddof=1)  # Use sample std (ddof=1)
            if std == 0 or np.isnan(std) or std == 0.0:
                return np.nan
            # Calculate excess kurtosis
            normalized = (x_arr - mean) / std
            fourth_moment = np.mean(normalized ** 4)
            # Excess kurtosis (subtract 3 for normal distribution)
            kurt = fourth_moment - 3.0
            return float(kurt) if not np.isnan(kurt) else np.nan
        
        df['kurtosis_20'] = df['returns'].rolling(window=20).apply(
            calc_kurtosis, raw=False
        )
        
        return df
    
    def _add_regime_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add regime indicators."""
        # Trend regime
        df['trend_up'] = (df['close'] > df['sma_200']).astype(int)
        df['trend_down'] = (df['close'] < df['sma_200']).astype(int)
        
        return df
    
    # Fallback implementations
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI without TA-Lib."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD without TA-Lib."""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist
    
    def _calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate ATR without TA-Lib."""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def _calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate ADX without TA-Lib."""
        # Simplified ADX calculation
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = self._calculate_atr(high, low, close, period)
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        return adx


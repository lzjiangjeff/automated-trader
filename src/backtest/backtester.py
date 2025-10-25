# src/backtest/backtester.py
import numpy as np
import pandas as pd

class Backtester:
    """
    Simple backtester for TQQQ strategies.
    Expects df with columns: open, high, low, close, volume
    """

    def __init__(self, df: pd.DataFrame, config: dict = None):
        if 'close' not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")
        self.df = df.copy()
        self.config = config or {}
        self.results = {}

    def run_trend_strategy(self):
        df = self.df.copy()
        df['ma50'] = df['close'].rolling(50).mean()
        df['position'] = 0

        # Use iloc for integer-based slicing with DatetimeIndex
        df.iloc[50:, df.columns.get_loc('position')] = np.where(
            df.iloc[50:, df.columns.get_loc('close')] > df.iloc[50:, df.columns.get_loc('ma50')],
            1,
            0
        )
        df['position'] = df['position'].fillna(0)

        self.results['trend'] = self._calculate_performance(df)
        return self.results['trend']

    def run_mean_reversion_strategy(self):
        df = self.df.copy()
        df['ma20'] = df['close'].rolling(20).mean()
        df['std20'] = df['close'].rolling(20).std()
        df['z_score'] = (df['close'] - df['ma20']) / df['std20']
        df['position'] = 0

        df.iloc[20:, df.columns.get_loc('position')] = np.where(
            df.iloc[20:, df.columns.get_loc('z_score')] < -1,
            1,
            np.where(df.iloc[20:, df.columns.get_loc('z_score')] > 1, -1, 0)
        )
        df['position'] = df['position'].fillna(0)

        self.results['mean_reversion'] = self._calculate_performance(df)
        return self.results['mean_reversion']

    def run_vol_momentum_strategy(self):
        df = self.df.copy()
        df['ret'] = df['close'].pct_change()
        df['vol'] = df['ret'].rolling(20).std()
        df['momentum'] = df['close'].pct_change(10)
        df['position'] = 0

        df.iloc[20:, df.columns.get_loc('position')] = np.where(
            df.iloc[20:, df.columns.get_loc('momentum')] > 0,
            1,
            -1
        )
        df['position'] = df['position'].fillna(0)

        self.results['vol_momentum'] = self._calculate_performance(df)
        return self.results['vol_momentum']

    def _calculate_performance(self, df: pd.DataFrame) -> dict:
        """
        Calculates equity curve and risk metrics
        """
        df = df.copy()
        df['strategy_ret'] = df['position'].shift(1) * df['close'].pct_change()
        df['equity_curve'] = (1 + df['strategy_ret'].fillna(0)).cumprod()

        total_return = df['equity_curve'].iloc[-1] - 1
        ann_return = (df['equity_curve'].iloc[-1]) ** (252 / len(df)) - 1
        sharpe = df['strategy_ret'].mean() / df['strategy_ret'].std() * np.sqrt(252) if df['strategy_ret'].std() != 0 else 0
        max_dd = (df['equity_curve'].cummax() - df['equity_curve']).max()

        return {
            'equity_curve': df['equity_curve'],
            'metrics': {
                'total_return': total_return,
                'ann_return': ann_return,
                'sharpe': sharpe,
                'max_drawdown': max_dd
            }
        }

    def run_all(self):
        self.run_trend_strategy()
        self.run_mean_reversion_strategy()
        self.run_vol_momentum_strategy()
        return self.results

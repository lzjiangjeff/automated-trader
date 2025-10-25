
import pandas as pd
import numpy as np
from src.strategies.trend import strategy as trend_strategy
from src.strategies.mean_reversion import strategy as mr_strategy
from src.strategies.vol_momentum import strategy as vm_strategy

class BacktestEngine:
    def __init__(self, df, config=None):
        self.df = df.copy()
        self.config = config or {}
        self.results = {}

    def run_strategy(self, signal, name='strategy'):
        df = self.df.copy()
        df['signal'] = signal.shift(1).fillna(0)  # simple next-day execution
        df['returns'] = df['c'].pct_change().fillna(0)
        df['strategy_returns'] = df['signal'] * df['returns']
        cum = (1 + df['strategy_returns']).cumprod()
        total_return = cum.iloc[-1] - 1
        ann_return = (1 + total_return) ** (252 / len(df)) - 1 if len(df) > 0 else 0
        sharpe = df['strategy_returns'].mean() / (df['strategy_returns'].std() + 1e-9) * (252**0.5)
        maxdd = self.max_drawdown(cum)
        return {
            'total_return': float(total_return),
            'ann_return': float(ann_return),
            'sharpe': float(sharpe),
            'max_drawdown': float(maxdd)
        }

    def max_drawdown(self, cumulative):
        peak = cumulative.cummax()
        dd = (cumulative - peak) / peak
        return dd.min()

    def run_all_strategies(self):
        s1 = trend_strategy(self.df)
        s2 = mr_strategy(self.df)
        s3 = vm_strategy(self.df)
        self.results['trend'] = self.run_strategy(s1, 'trend')
        self.results['mean_reversion'] = self.run_strategy(s2, 'mean_reversion')
        self.results['vol_momentum'] = self.run_strategy(s3, 'vol_momentum')
        return self.results

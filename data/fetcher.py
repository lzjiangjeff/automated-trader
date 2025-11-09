"""Data fetching module for market data."""

import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import pickle


class DataFetcher:
    """Fetches and caches market data."""
    
    def __init__(self, cache_dir: str = "data/"):
        """Initialize data fetcher.
        
        Args:
            cache_dir: Directory to cache data files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        interval: str = "1d",
        use_cache: bool = True
    ) -> pd.DataFrame:
        """Fetch data for a symbol.
        
        Args:
            symbol: Symbol to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD) or None for today
            interval: Data interval (1d, 1h, etc.)
            use_cache: Whether to use cached data if available
        
        Returns:
            DataFrame with OHLCV data
        """
        cache_file = self.cache_dir / f"{symbol}_{interval}_{start_date}_{end_date or 'latest'}.pkl"
        
        if use_cache and cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if df.empty:
            raise ValueError(f"No data found for {symbol}")
        
        # Standardize column names
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        df.index.name = 'date'
        df = df.reset_index()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Forward fill missing values
        df = df.ffill()
        df = df.dropna()
        
        # Save to cache
        if use_cache:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
        
        return df
    
    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        interval: str = "1d",
        use_cache: bool = True
    ) -> dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols.
        
        Args:
            symbols: List of symbols to fetch
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD) or None for today
            interval: Data interval
            use_cache: Whether to use cached data
        
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        for symbol in symbols:
            try:
                data[symbol] = self.fetch_symbol(
                    symbol, start_date, end_date, interval, use_cache
                )
            except Exception as e:
                print(f"Warning: Failed to fetch {symbol}: {e}")
        return data


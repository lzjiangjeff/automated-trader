"""Base strategy class."""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, config: Dict):
        """Initialize strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, context: Optional[Dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
        """Generate trading signals.
        
        Args:
            df: Primary symbol DataFrame with features
            context: Optional dictionary of context symbol DataFrames
        
        Returns:
            DataFrame with signal column (1 for long, -1 for short, 0 for neutral)
        """
        pass
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate that required columns exist.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            True if valid, raises ValueError otherwise
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return True


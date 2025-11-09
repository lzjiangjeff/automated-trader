"""SQLite database module for storing backtest results."""

import sqlite3
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BacktestDatabase:
    """SQLite database for storing backtest results."""
    
    def __init__(self, db_path: str = "data/backtests.db"):
        """Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Backtest runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                config_path TEXT,
                config_json TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                symbol TEXT NOT NULL,
                initial_capital REAL NOT NULL,
                final_equity REAL,
                status TEXT DEFAULT 'completed'
            )
        """)
        
        # Equity curve table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                equity REAL NOT NULL,
                FOREIGN KEY (backtest_id) REFERENCES backtest_runs(id)
            )
        """)
        
        # Returns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                return_pct REAL NOT NULL,
                FOREIGN KEY (backtest_id) REFERENCES backtest_runs(id)
            )
        """)
        
        # Trade log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                side TEXT NOT NULL,
                shares INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                exit_reason TEXT,
                pnl REAL NOT NULL,
                r_multiple REAL,
                bars_in_trade INTEGER,
                strategy TEXT,
                FOREIGN KEY (backtest_id) REFERENCES backtest_runs(id)
            )
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                FOREIGN KEY (backtest_id) REFERENCES backtest_runs(id),
                UNIQUE(backtest_id, metric_name)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equity_curve_backtest ON equity_curve(backtest_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equity_curve_date ON equity_curve(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_returns_backtest ON returns(backtest_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_backtest ON trades(backtest_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_backtest ON metrics(backtest_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def save_backtest(
        self,
        results: Dict,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        start_date: str = None,
        end_date: Optional[str] = None,
        symbol: str = "TQQQ",
        initial_capital: float = 100000
    ) -> int:
        """Save backtest results to database.
        
        Args:
            results: Backtest results dictionary
            config_path: Path to config file
            config_dict: Configuration dictionary
            start_date: Start date
            end_date: End date
            symbol: Symbol traded
            initial_capital: Initial capital
        
        Returns:
            Backtest ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get timestamp
        timestamp = datetime.now().isoformat()
        
        # Get final equity
        if 'equity_curve' in results and len(results['equity_curve']) > 0:
            final_equity = results['equity_curve'].iloc[-1]
        else:
            final_equity = initial_capital
        
        # Insert backtest run
        cursor.execute("""
            INSERT INTO backtest_runs 
            (timestamp, config_path, config_json, start_date, end_date, symbol, initial_capital, final_equity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            config_path,
            json.dumps(config_dict) if config_dict else None,
            start_date,
            end_date,
            symbol,
            initial_capital,
            final_equity,
            'completed'
        ))
        
        backtest_id = cursor.lastrowid
        
        # Save equity curve
        if 'equity_curve' in results:
            equity_curve = results['equity_curve']
            for date, equity in equity_curve.items():
                cursor.execute("""
                    INSERT INTO equity_curve (backtest_id, date, equity)
                    VALUES (?, ?, ?)
                """, (backtest_id, date.isoformat(), equity))
        
        # Save returns
        if 'returns' in results:
            returns = results['returns']
            for date, ret in returns.items():
                cursor.execute("""
                    INSERT INTO returns (backtest_id, date, return_pct)
                    VALUES (?, ?, ?)
                """, (backtest_id, date.isoformat(), ret * 100))
        
        # Save trades
        if 'trade_log' in results:
            for trade in results['trade_log']:
                # Handle entry_date
                entry_date = trade.get('entry_date')
                if hasattr(entry_date, 'isoformat'):
                    entry_date_str = entry_date.isoformat()
                elif isinstance(entry_date, str):
                    entry_date_str = entry_date
                else:
                    entry_date_str = str(entry_date)
                
                # Handle exit_date
                exit_date = trade.get('exit_date')
                if hasattr(exit_date, 'isoformat'):
                    exit_date_str = exit_date.isoformat()
                elif isinstance(exit_date, str):
                    exit_date_str = exit_date
                else:
                    exit_date_str = str(exit_date)
                
                cursor.execute("""
                    INSERT INTO trades 
                    (backtest_id, entry_date, exit_date, side, shares, entry_price, exit_price, 
                     stop_price, exit_reason, pnl, r_multiple, bars_in_trade, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    backtest_id,
                    entry_date_str,
                    exit_date_str,
                    trade.get('side', ''),
                    trade.get('shares', 0),
                    trade.get('entry_price', 0.0),
                    trade.get('exit_price', 0.0),
                    trade.get('stop_price', 0.0),
                    trade.get('exit_reason', ''),
                    trade.get('pnl', 0.0),
                    trade.get('r_multiple', 0.0),
                    trade.get('bars_in_trade', 0),
                    trade.get('strategy', '')
                ))
        
        # Save metrics
        if 'metrics' in results:
            for metric_name, metric_value in results['metrics'].items():
                cursor.execute("""
                    INSERT OR REPLACE INTO metrics (backtest_id, metric_name, metric_value)
                    VALUES (?, ?, ?)
                """, (backtest_id, metric_name, metric_value))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved backtest {backtest_id} to database")
        return backtest_id
    
    def get_backtest_runs(self, limit: int = 10) -> pd.DataFrame:
        """Get list of backtest runs.
        
        Args:
            limit: Maximum number of runs to return
        
        Returns:
            DataFrame with backtest runs
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT id, timestamp, config_path, start_date, end_date, symbol, 
                   initial_capital, final_equity, status
            FROM backtest_runs
            ORDER BY timestamp DESC
            LIMIT ?
        """, conn, params=(limit,))
        conn.close()
        return df
    
    def get_backtest_by_id(self, backtest_id: int) -> Optional[Dict]:
        """Get backtest results by ID.
        
        Args:
            backtest_id: Backtest ID
        
        Returns:
            Dictionary with backtest results or None
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get backtest run info
        run_df = pd.read_sql_query("""
            SELECT * FROM backtest_runs WHERE id = ?
        """, conn, params=(backtest_id,))
        
        if run_df.empty:
            conn.close()
            return None
        
        run_info = run_df.iloc[0].to_dict()
        
        # Get equity curve
        equity_df = pd.read_sql_query("""
            SELECT date, equity FROM equity_curve
            WHERE backtest_id = ?
            ORDER BY date
        """, conn, params=(backtest_id,))
        
        if not equity_df.empty:
            equity_df['date'] = pd.to_datetime(equity_df['date'])
            equity_df = equity_df.set_index('date')
            equity_curve = equity_df['equity']
        else:
            equity_curve = pd.Series()
        
        # Get returns
        returns_df = pd.read_sql_query("""
            SELECT date, return_pct FROM returns
            WHERE backtest_id = ?
            ORDER BY date
        """, conn, params=(backtest_id,))
        
        if not returns_df.empty:
            returns_df['date'] = pd.to_datetime(returns_df['date'])
            returns_df = returns_df.set_index('date')
            returns = returns_df['return_pct'] / 100.0
        else:
            returns = pd.Series()
        
        # Get trades
        trades_df = pd.read_sql_query("""
            SELECT * FROM trades
            WHERE backtest_id = ?
            ORDER BY entry_date
        """, conn, params=(backtest_id,))
        
        if not trades_df.empty:
            trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
            trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date'])
            trade_log = trades_df.to_dict('records')
        else:
            trade_log = []
        
        # Get metrics
        metrics_df = pd.read_sql_query("""
            SELECT metric_name, metric_value FROM metrics
            WHERE backtest_id = ?
        """, conn, params=(backtest_id,))
        
        if not metrics_df.empty:
            metrics = metrics_df.set_index('metric_name')['metric_value'].to_dict()
        else:
            metrics = {}
        
        conn.close()
        
        return {
            'backtest_id': backtest_id,
            'run_info': run_info,
            'equity_curve': equity_curve,
            'returns': returns,
            'trade_log': trade_log,
            'metrics': metrics
        }
    
    def get_equity_curve(self, backtest_id: int) -> pd.Series:
        """Get equity curve for a backtest.
        
        Args:
            backtest_id: Backtest ID
        
        Returns:
            Series with equity curve
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT date, equity FROM equity_curve
            WHERE backtest_id = ?
            ORDER BY date
        """, conn, params=(backtest_id,))
        conn.close()
        
        if df.empty:
            return pd.Series()
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return df['equity']
    
    def get_trades(self, backtest_id: int) -> pd.DataFrame:
        """Get trades for a backtest.
        
        Args:
            backtest_id: Backtest ID
        
        Returns:
            DataFrame with trades
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT * FROM trades
            WHERE backtest_id = ?
            ORDER BY entry_date
        """, conn, params=(backtest_id,))
        conn.close()
        
        if not df.empty:
            df['entry_date'] = pd.to_datetime(df['entry_date'])
            df['exit_date'] = pd.to_datetime(df['exit_date'])
        
        return df
    
    def get_metrics(self, backtest_id: int) -> Dict:
        """Get metrics for a backtest.
        
        Args:
            backtest_id: Backtest ID
        
        Returns:
            Dictionary with metrics
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT metric_name, metric_value FROM metrics
            WHERE backtest_id = ?
        """, conn, params=(backtest_id,))
        conn.close()
        
        if df.empty:
            return {}
        
        return df.set_index('metric_name')['metric_value'].to_dict()
    
    def delete_backtest(self, backtest_id: int) -> bool:
        """Delete a backtest and all associated data.
        
        Args:
            backtest_id: Backtest ID
        
        Returns:
            True if deleted successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Delete in order (respecting foreign key constraints)
            cursor.execute("DELETE FROM equity_curve WHERE backtest_id = ?", (backtest_id,))
            cursor.execute("DELETE FROM returns WHERE backtest_id = ?", (backtest_id,))
            cursor.execute("DELETE FROM trades WHERE backtest_id = ?", (backtest_id,))
            cursor.execute("DELETE FROM metrics WHERE backtest_id = ?", (backtest_id,))
            cursor.execute("DELETE FROM backtest_runs WHERE id = ?", (backtest_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Deleted backtest {backtest_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backtest {backtest_id}: {e}")
            conn.rollback()
            conn.close()
            return False


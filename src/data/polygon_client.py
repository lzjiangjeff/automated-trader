
import os, time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class PolygonClient:
    def __init__(self, api_key_env='POLYGON_API_KEY', cache_dir='data'):
        self.api_key = os.getenv(api_key_env)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base = 'https://api.polygon.io'
        self.cache_path = None

    def _daily_url(self, symbol, from_date=None, to_date=None):
        return f"{self.base}/v2/aggs/ticker/{symbol}/range/1/day/{from_date}/{to_date}?adjusted=true&sort=asc&limit=50000&apiKey={self.api_key}"

    def download_daily(self, symbol, from_date='1900-01-01', to_date=None):
        if not self.api_key:
            raise ValueError('POLYGON_API_KEY not set in environment. Copy .env.example to .env and set it.')
        if to_date is None:
            to_date = datetime.utcnow().strftime('%Y-%m-%d')
        url = self._daily_url(symbol, from_date, to_date)
        resp = requests.get(url, timeout=30)
        if resp.status_code == 429:
            raise RuntimeError('Rate limited by Polygon.io (429). Consider paid plan or slower requests.')
        resp.raise_for_status()
        data = resp.json()
        if 'results' not in data:
            raise RuntimeError(f'No results returned: {data}')
        rows = []
        for r in data['results']:
            rows.append({
                't': pd.to_datetime(r['t'], unit='ms'),
                'o': r['o'],
                'h': r['h'],
                'l': r['l'],
                'c': r['c'],
                'v': r['v'],
            })
        df = pd.DataFrame(rows).set_index('t').sort_index()
        self.cache_path = str(self.cache_dir / f"{symbol}_daily.parquet")
        df.to_parquet(self.cache_path)
        return df

    def load_cached(self, symbol='TQQQ', frequency='1d'):
        path = self.cache_dir / f"{symbol}_daily.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Cached data not found at {path}. Run update-data first.")
        df = pd.read_parquet(path)
        return df

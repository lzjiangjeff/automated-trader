import os
import time
import pandas as pd
import requests
from datetime import datetime, timedelta


class PolygonClient:
    """
    Polygon.io API client for fetching, caching, and loading historical stock data.
    """

    def __init__(self, api_key=None, cache_dir="data/cache"):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY not set. Please export it or add it to your .env file.")
        self.base_url = "https://api.polygon.io/v2"
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal request helper with retry logic
    # ------------------------------------------------------------------
    def _request(self, url, params=None, max_retries=3):
        params = params or {}
        params["apiKey"] = self.api_key

        for attempt in range(1, max_retries + 1):
            try:
                r = requests.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    return r.json()
                else:
                    print(f"[!] HTTP {r.status_code} from Polygon API: {r.text}")
            except requests.exceptions.RequestException as e:
                print(f"[!] API request failed (attempt {attempt}/{max_retries}): {e}")
            time.sleep(2 * attempt)

        print("[!] All retries failed.")
        return None

    # ------------------------------------------------------------------
    # Fetch and process historical data
    # ------------------------------------------------------------------
    def get_historic_data(self, symbol, start="2010-01-01", end=None):
        """
        Fetch historical daily OHLCV data for the given symbol.
        Returns a pandas DataFrame.
        """
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        print(f"Downloading {symbol} data from {start} to {end}...")

        url = f"{self.base_url}/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        data = self._request(url)

        if not data or "results" not in data:
            print(f"[!] No data received for {symbol}. Check your API key or symbol.")
            return pd.DataFrame()

        results = data.get("results", [])
        if not results:
            print(f"[!] No results found for {symbol}.")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(results)
        if df.empty:
            print(f"[!] Empty dataframe for {symbol}.")
            return pd.DataFrame()

        # Convert timestamps and rename columns
        df["t"] = pd.to_datetime(df["t"], unit="ms")
        df.rename(columns={
            "t": "date",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        }, inplace=True)

        # Sort chronologically and reset index
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    # ------------------------------------------------------------------
    # Save data to local cache
    # ------------------------------------------------------------------
    def update_data(self, symbol):
        """
        Fetch latest data for a symbol and save it to a local parquet cache.
        """
        df = self.get_historic_data(symbol)

        if df is None or df.empty:
            print(f"[!] No data to save for {symbol}. Skipping cache write.")
            return

        cache_path = os.path.join(self.cache_dir, f"{symbol}.parquet")
        try:
            df.to_parquet(cache_path)
            print(f"[✓] Data saved to cache: {cache_path}")
        except Exception as e:
            print(f"[!] Failed to save parquet for {symbol}: {e}")

    # ------------------------------------------------------------------
    # Load data from local cache
    # ------------------------------------------------------------------
    def load_cached(self, symbol):
        """
        Load cached parquet file for a symbol if available.
        Returns a pandas DataFrame.
        """
        cache_path = os.path.join(self.cache_dir, f"{symbol}.parquet")

        if not os.path.exists(cache_path):
            print(f"[!] No cached data found for {symbol}. Try running update-data first.")
            return None

        try:
            df = pd.read_parquet(cache_path)
            if df is None or df.empty:
                print(f"[!] Cached file for {symbol} is empty.")
                return None
            print(f"[✓] Loaded cached data for {symbol} from {cache_path}")
            return df
        except Exception as e:
            print(f"[!] Failed to read cached parquet for {symbol}: {e}")
            return None
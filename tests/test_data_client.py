
import os
from src.data.polygon_client import PolygonClient

def test_missing_key():
    # Temporarily unset env var if present
    import os
    old = os.environ.pop('POLYGON_API_KEY', None)
    client = PolygonClient()
    try:
        try:
            client.download_daily('TQQQ')
            assert False, 'Expected ValueError when API key missing'
        except ValueError:
            pass
    finally:
        if old is not None:
            os.environ['POLYGON_API_KEY'] = old

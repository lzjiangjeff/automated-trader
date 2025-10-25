
import os
from dotenv import load_dotenv
load_dotenv()
def ensure_env():
    from os import getenv
    key = getenv('POLYGON_API_KEY')
    return bool(key)

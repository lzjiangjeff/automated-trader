
import pandas as pd
def strategy(df, fast=20, slow=100):
    price = df['c']
    ma_fast = price.rolling(fast).mean()
    ma_slow = price.rolling(slow).mean()
    signal = (ma_fast > ma_slow).astype(int)  # 1 or 0
    return signal

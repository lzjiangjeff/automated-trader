
import pandas as pd
def strategy(df, window=20, z_entry=1.5):
    price = df['c']
    ret = price.pct_change().fillna(0)
    mean = ret.rolling(window).mean()
    std = ret.rolling(window).std()
    z = (ret - mean) / (std + 1e-9)
    signal = (z < -z_entry).astype(int)  # buy when z < -z_entry
    return signal

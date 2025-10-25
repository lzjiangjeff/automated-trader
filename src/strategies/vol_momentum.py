
import pandas as pd
def strategy(df, window=20):
    price = df['c']
    mom = price.pct_change(window).fillna(0)
    vol = price.pct_change().rolling(window).std().fillna(0)
    # volatility scaled momentum: sign(mom) * (abs(mom)/vol) clipped
    score = mom / (vol + 1e-9)
    signal = (score > 0).astype(int)
    return signal

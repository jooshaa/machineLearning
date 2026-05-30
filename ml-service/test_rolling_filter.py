import pandas as pd
import numpy as np

path = "data/raw/mbo/NQ/NQ/2026-05-14.parquet"
try:
    mbo_df = pd.read_parquet(path, columns=['ts_event', 'price', 'size', 'action', 'side', 'order_id'])
except:
    mbo_df = pd.read_parquet(path, columns=['price', 'size', 'action', 'side', 'order_id'])

median_price = mbo_df['price'].median()
if median_price > 1e8: mbo_df['price'] /= 1e9
elif median_price > 1e5: mbo_df['price'] /= 1e4

trades_only = mbo_df[mbo_df['action'] == 'T'].copy()
trades_only['size'] = trades_only['size'].astype('int64')

orig_len = len(trades_only)

# Spike filter with rolling 11-tick median
rolling_med = trades_only['price'].rolling(11, center=True).median().fillna(method='bfill').fillna(method='ffill')
SPIKE_THRESHOLD = 30
trades_only = trades_only[np.abs(trades_only['price'] - rolling_med) <= SPIKE_THRESHOLD]

print(f"Original trades: {orig_len}")
print(f"Filtered trades: {len(trades_only)}")
print(f"Removed: {orig_len - len(trades_only)} spikes")

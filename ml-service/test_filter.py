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

if not isinstance(trades_only.index, pd.DatetimeIndex):
    trades_only = trades_only.set_index('ts')
trades_only.index = pd.to_datetime(trades_only.index).tz_localize(None) if pd.to_datetime(trades_only.index).tz is None else pd.to_datetime(trades_only.index).tz_convert(None)

orig_len = len(trades_only)

# Spike filter
prices_10s = trades_only['price'].resample('10s').median().ffill().bfill()
rolling_med = prices_10s.rolling(window=12, min_periods=1).median() # 2 minutes
trades_10s_idx = trades_only.index.floor('10s')
ref_prices = rolling_med.loc[trades_10s_idx].values

SPIKE_THRESHOLD = 40
trades_only = trades_only[np.abs(trades_only['price'] - ref_prices) <= SPIKE_THRESHOLD]

print(f"Original trades: {orig_len}")
print(f"Filtered trades: {len(trades_only)}")
print(f"Removed: {orig_len - len(trades_only)} spikes")

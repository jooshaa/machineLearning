import pandas as pd
import numpy as np
from app.engine.features import extract_l3_features
import strategy_volume_delta as svd

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
    trades_only = trades_only.set_index('ts_event' if 'ts_event' in trades_only.columns else 'ts')
trades_only.index = pd.to_datetime(trades_only.index).tz_localize(None) if pd.to_datetime(trades_only.index).tz is None else pd.to_datetime(trades_only.index).tz_convert(None)

# Spike filter
prices_10s = trades_only['price'].resample('10s').median().ffill().bfill()
rolling_med = prices_10s.rolling(window=12, min_periods=1).median()
trades_10s_idx = trades_only.index.floor('10s')
ref_prices = rolling_med.loc[trades_10s_idx].values
trades_only = trades_only[np.abs(trades_only['price'] - ref_prices) <= 40]

impulses = svd.find_impulses(trades_only)
print(f"Total impulses: {len(impulses)}")

for imp in impulses:
    profile = svd.build_volume_profile(trades_only, imp['start'], imp['stop'])
    price_stop = imp['price_stop']
    price_start = imp['price_start']
    full_range = abs(price_stop - price_start)
    zone_depth = full_range * 0.3
    
    if imp['type'] == 'up':
        zone_low = price_stop - zone_depth
        zone_high = price_stop + 10
    else:
        zone_low = price_stop - 10
        zone_high = price_stop + zone_depth
        
    stopping_profile = profile[(profile.index >= zone_low) & (profile.index <= zone_high)]
    print(f"\n{imp['type'].upper()} impulse stopping profile (top 3 prices by volume):")
    if not stopping_profile.empty:
        print(stopping_profile.sort_values('volume', ascending=False).head(3))
        print(f"Min delta in zone: {stopping_profile['delta'].min()}")
        print(f"Max delta in zone: {stopping_profile['delta'].max()}")
        
        zones = svd.find_delta_zones(profile, imp)
        print(f"Valid zone generated: {zones['zone_price'] if zones['zone_price'] is not None and abs(zones['zone_delta']) >= 50 else 'NO'}")


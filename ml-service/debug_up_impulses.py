import pandas as pd
from app.engine.features import extract_l3_features
import strategy_volume_delta as svd

print("Loading data...")
path = "data/raw/mbo/NQ/NQ/2026-05-14.parquet"
try:
    mbo_df = pd.read_parquet(path, columns=['ts_event', 'price', 'size', 'action', 'side', 'order_id'])
except:
    mbo_df = pd.read_parquet(path, columns=['price', 'size', 'action', 'side', 'order_id'])

median_price = mbo_df['price'].median()
if median_price > 1e8: mbo_df['price'] /= 1e9
elif median_price > 1e5: mbo_df['price'] /= 1e4

trades_only = mbo_df[mbo_df['action'] == 'T'].copy()
median_price = trades_only['price'].median()
trades_only = trades_only[
    (trades_only['price'] > median_price * 0.5) &
    (trades_only['price'] < median_price * 1.5)
]

print("Finding impulses...")
impulses = svd.find_impulses(trades_only)

up_imps = [i for i in impulses if i['type'] == 'up']
down_imps = [i for i in impulses if i['type'] == 'down']

print(f"Total impulses: {len(impulses)}")
print(f"UP impulses: {len(up_imps)}")
print(f"DOWN impulses: {len(down_imps)}")

up_zones = 0
down_zones = 0
for imp in up_imps:
    profile = svd.build_volume_profile(trades_only, imp['start'], imp['stop'])
    zones = svd.find_delta_zones(profile, imp)
    if zones['buy']: up_zones += 1
for imp in down_imps:
    profile = svd.build_volume_profile(trades_only, imp['start'], imp['stop'])
    zones = svd.find_delta_zones(profile, imp)
    if zones['sell']: down_zones += 1

print(f"UP impulses with valid zones: {up_zones}")
print(f"DOWN impulses with valid zones: {down_zones}")

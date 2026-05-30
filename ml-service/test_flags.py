import pandas as pd
import numpy as np

path = "data/raw/mbo/NQ/NQ/2026-05-14.parquet"
df = pd.read_parquet(path, columns=['price', 'size', 'action', 'side', 'flags'])
trades_only = df[df['action'] == 'T'].copy()
trades_only['size'] = trades_only['size'].astype('int64')

median_price = trades_only['price'].median()
trades_only = trades_only[
    (trades_only['price'] > median_price * 0.5) &
    (trades_only['price'] < median_price * 1.5)
]

rolling_med = trades_only['price'].rolling(11, center=True).median().bfill().ffill()

spikes = trades_only[np.abs(trades_only['price'] - rolling_med) > 40]
print("Spike flags value counts:")
print(spikes['flags'].value_counts())

good_trades = trades_only[np.abs(trades_only['price'] - rolling_med) <= 40]
print("\nGood trades flags value counts:")
print(good_trades['flags'].value_counts())

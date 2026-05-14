import pandas as pd

d = "2025-03-05"
cache_path = f"data/raw/mbo/NQ/{d}.parquet"

mbo_df = pd.read_parquet(cache_path)
nqh5_bad = mbo_df[(mbo_df['symbol'] == 'NQH5') & (mbo_df['price'] < 10000)]
print(f"Bad prices in NQH5: {len(nqh5_bad)}")
if len(nqh5_bad) > 0:
    print(nqh5_bad[['action', 'side', 'price', 'size', 'symbol']].head())

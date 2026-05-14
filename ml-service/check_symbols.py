import pandas as pd

d = "2025-03-05"
cache_path = f"data/raw/mbo/NQ/{d}.parquet"

mbo_df = pd.read_parquet(cache_path)
print("Unique symbols in MBO DF:")
print(mbo_df['symbol'].unique())

bad_prices = mbo_df[mbo_df['price'] < 10000]
print("Unique symbols for price < 10000:")
print(bad_prices['symbol'].unique())

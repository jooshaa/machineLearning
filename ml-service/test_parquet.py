import pandas as pd
df = pd.read_parquet("data/raw/mbo/NQ/2023-01-03.parquet")
print(df.index.dtype)
print(df.index[0])
print(pd.Timestamp(df.index[0]).hour)

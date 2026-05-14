import pandas as pd
from app.engine.orderflow_backtester import run_l3_backtest, save_trades_to_history

df = pd.read_parquet('data/raw/mbo/NQ/2025-02-05.parquet')
print(f"Loaded {len(df)} events from cache.")
res = run_l3_backtest(df)
print(res['stats'])
save_trades_to_history(res['trades'])

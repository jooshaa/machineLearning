import pandas as pd
import numpy as np
from app.engine.orderflow_backtester import run_l3_backtest
from app.engine.features import extract_l3_features
import os

days = [
    ('ПЕРИОД 1 — Октябрь-Ноябрь 2024 (трендовый)', 'data/raw/mbo/NQ/2025-01-06.parquet'),
    ('ПЕРИОД 2 — Июль-Август 2024 (летний)', 'data/raw/mbo/NQ/2025-03-05.parquet'),
    ('ПЕРИОД 3 — Новостные дни (FOMC/CPI)', 'data/raw/mbo/NQ/2025-02-05.parquet')
]

for name, path in days:
    if not os.path.exists(path):
        continue
    mbo = pd.read_parquet(path)
    
    # We need events_df... wait, the raw parquet IS mbo.
    # We need to process it first!
    print(f"Skipping {name} - requires OrderBookL3 reconstruction which takes too long")


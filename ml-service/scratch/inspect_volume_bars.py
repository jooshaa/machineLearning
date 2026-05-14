
import pandas as pd
import numpy as np
import os
import sys
import warnings

# Add parent dir to path to import app modules correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream

warnings.filterwarnings('ignore')

try:
    d = "2025-01-13"
    symbol = "NQ.FUT"
    start = f"{d}T14:30:00"
    end = f"{d}T21:00:00"

    print("Loading data...")
    mbo_df = fetch_mbo_data(symbol, start, end)
    
    print("Processing stream...")
    events = process_mbo_stream(mbo_df)
    df = pd.DataFrame(events)
    df["ts"] = pd.to_datetime(df["ts"])
    df["delta"] = np.where(df["side"] == "A", df["size"], -df["size"])
    
    print("Aggregating into 500-contract volume bars...")
    df = df.copy().reset_index(drop=True)
    df["cum_vol"] = df["size"].cumsum()
    df["bar_id"] = (df["cum_vol"] // 500).astype(int)

    bars = df.groupby("bar_id").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        delta=("delta", "sum"),
        ts=("ts", "first"),
    )

    bars["delta_vol_ratio"] = abs(bars["delta"]) / (bars["volume"] + 1e-9)
    bars["range"] = bars["high"] - bars["low"]
    bars["range_mean"] = bars["range"].rolling(200).mean()

    print(f"\nБаров за день: {len(bars)}")
    print(f"Среднее delta/vol: {bars['delta_vol_ratio'].mean():.3f}")
    print(f"90й перцентиль delta/vol: {bars['delta_vol_ratio'].quantile(0.9):.3f}")
    print(f"Средний range: {bars['range'].mean():.2f}")
    print(f"10й перцентиль range: {bars['range'].quantile(0.1):.2f}")
    
except Exception as e:
    print(f"Error: {e}")

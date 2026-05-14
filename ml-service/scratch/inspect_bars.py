
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
    
    print("Aggregating into 1s bars...")
    df = df.set_index("ts")

    bars = df.resample("1s").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("size", "sum"),
        delta=("delta", "sum"),
    ).dropna()

    bars["delta_vol_ratio"] = abs(bars["delta"]) / (bars["volume"] + 1e-9)

    print(f"\nБаров за день: {len(bars)}")
    print(f"Среднее volume на бар: {bars['volume'].mean():.1f}")
    print(f"Среднее delta/vol: {bars['delta_vol_ratio'].mean():.3f}")
    print(f"Max delta/vol: {bars['delta_vol_ratio'].max():.3f}")
    print(f"Средний range бара (high-low): {(bars['high']-bars['low']).mean():.2f}")
    
except Exception as e:
    print(f"Error: {e}")

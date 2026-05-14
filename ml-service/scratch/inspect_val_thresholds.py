
import pandas as pd
import numpy as np
import os
import sys
import warnings

# Add parent dir to path to import app modules correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.orderflow_backtester import get_prev_day_profile

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
    events_df = pd.DataFrame(events)
    
    print("Extracting features...")
    events_df = extract_l3_features(mbo_df, events_df)
    
    # Calculate levels like in backtester
    poc, vah, val = get_prev_day_profile(d)
    
    if not val:
        print("Error: VAL not calculated.")
        sys.exit(1)

    near_val = events_df[abs(events_df['price'] - val) <= 50].copy()
    if near_val.empty:
        print("No events near VAL.")
        sys.exit(0)

    rolling_vol_30 = near_val["size"].rolling(30).sum()
    rolling_vol_mean = rolling_vol_30.rolling(200, min_periods=20).mean()
    price_range_30 = near_val["price"].rolling(30).max() - near_val["price"].rolling(30).min()
    price_range_mean = price_range_30.rolling(200, min_periods=20).mean()
    delta_30 = near_val["delta"].rolling(30).sum()

    print("\n=== Фактические значения у VAL ===")
    print(f"vol_30 среднее: {rolling_vol_30.mean():.1f}")
    print(f"vol_mean среднее: {rolling_vol_mean.mean():.1f}")
    print(f"vol_30 / vol_mean среднее: {(rolling_vol_30 / (rolling_vol_mean + 1e-9)).mean():.2f}")
    print(f"price_range_30 среднее: {price_range_30.mean():.2f}")
    print(f"price_range_mean среднее: {price_range_mean.mean():.2f}")
    print(f"range / range_mean среднее: {(price_range_30 / (price_range_mean + 1e-9)).mean():.2f}")
    print(f"abs(delta_30) / vol_30 среднее: {(abs(delta_30) / (rolling_vol_30 + 1e-9)).mean():.2f}")
    
except Exception as e:
    print(f"Error: {e}")

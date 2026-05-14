
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

cache_dir = "data/raw/mbo/NQ"
files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".parquet")])
dates = [f.replace(".parquet", "") for f in files]

symbol = "NQ.FUT"

print(f"{'Date':<12} | {'Prev VAH':<9} | {'Prev VAL':<9} | {'Day Low':<9} | {'Day High':<9} | {'VAL Touch'}")
print("-" * 75)

for d in dates:
    try:
        # Calculate levels from previous day
        poc, vah, val = get_prev_day_profile(d)
        
        if vah is None or val is None:
            print(f"{d:<12} | {'N/A':<9} | {'N/A':<9} | {'N/A':<9} | {'N/A':<9} | No Prev")
            continue

        # Load current day raw to get min/max quickly
        df = pd.read_parquet(f"{cache_dir}/{d}.parquet")
        low = df["price"].min()
        high = df["price"].max()
        
        # Check for touch
        val_touch = "YES" if (low <= val <= high) else "no"
        vah_touch = "YES" if (low <= vah <= high) else "no"
        
        touch_str = f"VAL:{val_touch} VAH:{vah_touch}"
        
        print(f"{d:<12} | {vah:<9.2f} | {val:<9.2f} | {low:<9.2f} | {high:<9.2f} | {touch_str}")
        
    except Exception as e:
        print(f"{d:<12} | Error: {e}")

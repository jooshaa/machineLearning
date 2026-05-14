
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
    
    print("Extracting features...")
    df = extract_l3_features(mbo_df, df)
    
    print("\n=== Распределение event_type (весь день) ===")
    print(df["event_type"].value_counts())

    # VAL из предыдущего дня
    val = 21173.78
    tolerance = 30
    near = df[abs(df["price"] - val) <= tolerance]
    
    print(f"\n=== Событий у VAL (21173.78 ± 30): {len(near)} ===")
    print(near["event_type"].value_counts())
    
except Exception as e:
    print(f"Error: {e}")

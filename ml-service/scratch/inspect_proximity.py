
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
    
    print(f"\nVAH: {vah}, VAL: {val}")
    print(f"ATR среднее: {events_df['atr'].mean() if 'atr' in events_df.columns else 'нет колонки atr'}")
    print(f"Диапазон цен дня: {events_df['price'].min():.2f} - {events_df['price'].max():.2f}")

    # Сколько событий было БЛИЗКО к VAH/VAL
    tolerance_test = 50  # грубо
    near_vah = events_df[abs(events_df['price'] - vah) <= tolerance_test] if vah else pd.DataFrame()
    near_val = events_df[abs(events_df['price'] - val) <= tolerance_test] if val else pd.DataFrame()
    print(f"Событий в 50 пунктах от VAH: {len(near_vah)}")
    print(f"Событий в 50 пунктах от VAL: {len(near_val)}")

    # Из них сколько absorption/trap
    if not near_vah.empty:
        print(f"Absorption у VAH: {near_vah['absorption_flag'].sum()}")
        print(f"Trap у VAH: {near_vah['trap_flag'].sum()}")
    if not near_val.empty:
        print(f"Absorption у VAL: {near_val['absorption_flag'].sum()}")
        print(f"Trap у VAL: {near_val['trap_flag'].sum()}")
    
except Exception as e:
    print(f"Error: {e}")

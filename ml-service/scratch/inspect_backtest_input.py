
import pandas as pd
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
    events_df = pd.DataFrame(events)
    
    print("Extracting features (this adds 'session' column)...")
    features = extract_l3_features(mbo_df, events_df)
    
    # This is what happens in Fix 2
    ny_df = features[features["session"] == "NY"]
    
    print(f"Всего строк (features): {len(features)}")
    print(f"NY строк: {len(ny_df)}")
    print(f"Сессии в данных: {features['session'].unique()}")
    if not ny_df.empty:
        print(f"Диапазон цен NY: {ny_df['price'].min():.2f} - {ny_df['price'].max():.2f}")
    print(f"Диапазон дат: {features['ts'].min()} - {features['ts'].max()}")
    
except Exception as e:
    print(f"Error: {e}")

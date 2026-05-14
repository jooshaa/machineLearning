
import pandas as pd
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
    events_df = pd.DataFrame(events)
    
    # User's suggested filter
    events_df["ts"] = pd.to_datetime(events_df["ts"])
    ny_session_df = events_df[
        (events_df["ts"].dt.tz_convert("US/Eastern").dt.time >= pd.to_datetime("09:30").time()) &
        (events_df["ts"].dt.tz_convert("US/Eastern").dt.time < pd.to_datetime("16:00").time())
    ]
    
    print(f"Всего строк в events_df: {len(events_df)}")
    print(f"Строк в ny_session_df: {len(ny_session_df)}")
    if not ny_session_df.empty:
        print(f"Диапазон цен NY: {ny_session_df['price'].min():.2f} - {ny_session_df['price'].max():.2f}")
        print(f"Диапазон времени NY (US/Eastern): {ny_session_df['ts'].dt.tz_convert('US/Eastern').min()} - {ny_session_df['ts'].dt.tz_convert('US/Eastern').max()}")
    
except Exception as e:
    print(f"Error: {e}")

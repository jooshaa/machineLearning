
import pandas as pd
import os
import sys
import warnings

# Add parent dir to path to import app modules correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules

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
    features = extract_l3_features(mbo_df, events_df)
    features = compute_context(features)
    
    print("\n--- COLUMNS ---")
    print(features.columns.tolist())
    
    print("\n--- FIRST 5 ROWS ---")
    cols_to_show = ["ts", "price", "vol"]
    available_cols = [c for c in cols_to_show if c in features.columns]
    if "session" in features.columns:
        available_cols.append("session")
    
    print(features[available_cols].head(5))
    
except Exception as e:
    print(f"Error: {e}")

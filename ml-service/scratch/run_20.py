
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
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest

warnings.filterwarnings('ignore')

try:
    d = "2025-01-20"
    symbol = "NQ.FUT"
    start = f"{d}T14:30:00"
    end = f"{d}T21:00:00"

    print(f"Loading {d} from cache...")
    mbo_df = fetch_mbo_data(symbol, start, end)
    
    print("Processing stream...")
    events = process_mbo_stream(mbo_df)
    events_df = pd.DataFrame(events)
    
    print("Extracting features...")
    features = extract_l3_features(mbo_df, events_df)
    features = compute_context(features)
    features = compute_sequence(features)
    features = score_events(features)
    features = apply_decision_rules(features)
    
    print("Running backtest...")
    res = run_l3_backtest(features)
    
    funnel = res.get('funnel', {})
    stats = res.get('stats', {})
    
    print(f"\n--- RESULTS {d} ---")
    print(f"Absorption: {features['absorption_flag'].sum() if 'absorption_flag' in features.columns else 0}")
    print(f"Trap: {features['trap_flag'].sum() if 'trap_flag' in features.columns else 0}")
    print(f"passed_boundary: {funnel.get('passed_boundary', 0)}")
    print(f"passed_aggression: {funnel.get('passed_aggression', 0)}")
    print(f"Сделок: {stats.get('total_trades', 0)}")
    
    trades = res.get('trades', [])
    if trades:
        print("\n--- FIRST 3 TRADES ---")
        for t in trades[:3]:
            print(f"ts: {t.get('ts_entry')}, dir: {t.get('direction')}, entry: {t.get('entry_price')}, exit: {t.get('exit_price')}, res: {t.get('pnl'):.2f}")
    
except Exception as e:
    print(f"Error: {e}")

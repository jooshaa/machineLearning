
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
from app.engine.orderflow_backtester import run_l3_backtest

warnings.filterwarnings('ignore')

d = "2025-01-08"
symbol = "NQ.FUT"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

mbo_df = fetch_mbo_data(symbol, start, end)
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)
features = extract_l3_features(mbo_df, events_df)
features = compute_context(features)
features = compute_sequence(features)
features = score_events(features)
features = apply_decision_rules(features)

res = run_l3_backtest(features)
trades = res.get('trades', [])

for t in trades:
    if t.get('result') == 'loss':
        print(f"entry={t['entry_price']}, stop={t['stop']}, exit={t['exit_price']}, pnl_pts={t.get('pnl_pts')}")

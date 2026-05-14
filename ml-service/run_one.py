import sys
import pandas as pd
import warnings
from app.engine.orderflow_backtester import run_l3_backtest
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules

warnings.filterwarnings('ignore')

d = sys.argv[1]
symbol = "NQ.FUT"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

try:
    mbo_df = fetch_mbo_data(symbol, start, end)
    events = process_mbo_stream(mbo_df)
    events_df = pd.DataFrame(events)
    features = extract_l3_features(mbo_df, events_df)
    features = compute_context(features)
    features = compute_sequence(features)
    features = score_events(features)
    features = apply_decision_rules(features)
    res = run_l3_backtest(features)
    
    funnel = res.get('funnel', {})
    stats = res.get('stats', {})
    trades = res.get('trades', [])
    
    wins = sum(1 for t in trades if t['result'] == 'win')
    losses = sum(1 for t in trades if t['result'] == 'loss')
    
    print(f"[{d}] Boundary: {funnel.get('passed_boundary', 0)} | Aggression: {funnel.get('passed_aggression', 0)} | Trades: {stats.get('total_trades', 0)} | W/L: {wins}/{losses}")
except Exception as e:
    print(f"[{d}] Error: {str(e)}")

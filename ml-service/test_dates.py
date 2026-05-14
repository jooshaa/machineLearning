import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest
import warnings

warnings.filterwarnings('ignore')

dates = ["2025-01-13", "2025-01-22", "2025-02-19", "2025-03-05"]
symbol = "NQ.FUT"

for d in dates:
    print(f"\n--- Date: {d} ---")
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
    
    print(f"Количество сделок: {res['stats']['total_trades']}")
    print(f"Сетапов на VAH/VAL (passed_boundary): {res['funnel'].get('passed_boundary', 0)}")
    print(f"Первых импульсов (blocked_aggression): {res['funnel'].get('blocked_aggression', 0)}")
    print(f"Ретестов (passed_aggression): {res['funnel'].get('passed_aggression', 0)}")


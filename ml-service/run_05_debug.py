import pandas as pd
from app.engine.orderflow_backtester import run_l3_backtest
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
import warnings

warnings.filterwarnings('ignore')

d = "2025-03-05"
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
    
    trades = res.get('trades', [])
    for t in trades:
        print(f"Trade Details:")
        print(f"entry_price: {t.get('entry_price')}")
        print(f"stop: {t.get('stop')}")
        print(f"exit_price: {t.get('exit_price')}")
        print(f"direction: {t.get('direction')}")
        # To get volatility or calc_risk, maybe it's not saved in the trade dict.
        # But let's print the entire trade dict just in case.
        print(f"Full dict: {t}")
except Exception as e:
    print(f"Error: {e}")

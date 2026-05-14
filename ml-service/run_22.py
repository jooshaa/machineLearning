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

d = "2025-01-22"
symbol = "NQ.FUT"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

print(f"\n--- Processing {d} ---")
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
    
    print(f"Results for {d}:")
    print(f"- passed_boundary (сетапов найдено): {funnel.get('passed_boundary', 0)}")
    print(f"- passed_aggression (ретестов): {funnel.get('passed_aggression', 0)}")
    print(f"- Сделок всего: {stats.get('total_trades', 0)}")
    
    wins = sum(1 for t in trades if t['result'] == 'win')
    losses = sum(1 for t in trades if t['result'] == 'loss')
    print(f"- Win/Loss: {wins}/{losses}")
    
    if trades:
        for i, t in enumerate(trades):
            print(f"  Сделка {i+1}: {t['result']}, R: {t.get('outcome_R', 0):.2f}")
except Exception as e:
    print(f"Error processing {d}: {e}")

import pandas as pd
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest, save_trades_to_history

mbo_df = pd.read_parquet('data/raw/mbo/NQ/2025-02-05.parquet')
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)
features = extract_l3_features(mbo_df, events_df)
features = compute_context(features)
features = compute_sequence(features)
features = score_events(features)
features = apply_decision_rules(features)
res = run_l3_backtest(features)
print(f"Total trades generated: {len(res['trades'])}")
save_trades_to_history(res['trades'])

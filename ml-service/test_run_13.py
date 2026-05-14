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

d = "2025-01-13"
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

print(f"--- Результаты за {d} ---")
print(f"Funnel: {res['funnel']}")
print(f"Passed boundary: {res['funnel'].get('passed_boundary', 0)}")
print(f"Сделок: {res['stats']['total_trades']}")
print(f"Daily loss limit hit: {res['stats'].get('daily_loss_limit_hit', False)}")

print("\nПервые 5 сделок:")
for t in res['trades'][:5]:
    print(f"Direction: {t['direction']}, Entry: {t['entry_price']}, Exit: {t['exit_price']}, Result: {t['result']}, R: {t.get('outcome_R', 0):.2f}")

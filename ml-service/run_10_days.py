import pandas as pd
import warnings
import concurrent.futures
from app.engine.orderflow_backtester import run_l3_backtest
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules

warnings.filterwarnings('ignore')

dates = [
    "2025-01-14", "2025-01-15", "2025-01-23", "2025-01-24", 
    "2025-02-04", "2025-02-12", "2025-02-20", 
    "2025-03-03", "2025-03-06", "2025-03-12"
]
symbol = "NQ.FUT"

def process_date(d):
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
        
        return {
            "date": d,
            "passed_boundary": funnel.get('passed_boundary', 0),
            "passed_aggression": funnel.get('passed_aggression', 0),
            "total_trades": stats.get('total_trades', 0),
            "wins": wins,
            "losses": losses
        }
    except Exception as e:
        return {"date": d, "error": str(e)}

if __name__ == "__main__":
    results = []
    # Using max_workers=8 to prevent memory issues
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
        for res in executor.map(process_date, dates):
            if "error" in res:
                print(f"[{res['date']}] Error: {res['error']}")
            else:
                print(f"[{res['date']}] Boundary: {res['passed_boundary']} | Aggression: {res['passed_aggression']} | Trades: {res['total_trades']} | W/L: {res['wins']}/{res['losses']}")

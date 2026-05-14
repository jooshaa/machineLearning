
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

cache_dir = "data/raw/mbo/NQ"
files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".parquet")])
dates = [f.replace(".parquet", "") for f in files]

# Filter only 2025 dates for cleaner results
dates = [d for d in dates if d.startswith("2025")]

results = []
all_trades_global = []

print(f"Starting mass backtest on {len(dates)} dates...")

for d in dates:
    try:
        symbol = "NQ.FUT"
        start = f"{d}T14:30:00"
        end = f"{d}T21:00:00"

        mbo_df = fetch_mbo_data(symbol, start, end)
        if mbo_df.empty:
            continue
            
        events = process_mbo_stream(mbo_df)
        events_df = pd.DataFrame(events)
        if events_df.empty:
            continue
            
        features = extract_l3_features(mbo_df, events_df)
        features = compute_context(features)
        features = compute_sequence(features)
        features = score_events(features)
        features = apply_decision_rules(features)
        
        res = run_l3_backtest(features)
        stats = res.get('stats', {})
        trades = res.get('trades', [])
        
        all_trades_global.extend(trades)
        
        wins = sum(1 for t in trades if t.get('result') == 'win')
        losses = sum(1 for t in trades if t.get('result') == 'loss')
        total_pnl = sum(t.get('pnl_pts', 0) for t in trades)
        
        results.append({
            "Date": d,
            "Trades": stats.get('total_trades', 0),
            "Wins": wins,
            "Losses": losses,
            "PnL": round(total_pnl, 2),
            "WR%": f"{stats.get('win_rate', 0):.1f}%",
            "Total R": round(stats.get('total_R', 0), 2)
        })
        print(f"Done {d}: {stats.get('total_trades', 0)} trades, PnL (pts): {total_pnl:.2f}")
        
    except Exception as e:
        print(f"Error on {d}: {e}")

print("\n" + "="*80)
print(f"{'Date':<12} | {'Trades':<7} | {'Wins':<5} | {'Losses':<6} | {'PnL Pts':<10} | {'WR%':<7} | {'Total R'}")
print("-" * 80)
for r in results:
    print(f"{r['Date']:<12} | {r['Trades']:<7} | {r['Wins']:<5} | {r['Losses']:<6} | {r['PnL']:<10.2f} | {r['WR%']:<7} | {r['Total R']}")

total_trades = sum(r["Trades"] for r in results)
net_pnl = sum(r["PnL"] for r in results)
print("="*80)
print(f"TOTAL TRADES: {total_trades}")
print(f"NET PNL (pts): {net_pnl:.2f}")

if all_trades_global:
    df_all = pd.DataFrame(all_trades_global)
    tp_count = (df_all['exit_reason'] == 'target').sum()
    sl_count = (df_all['exit_reason'] == 'stop').sum()
    eod_count = (df_all['exit_reason'] == 'closed_eod').sum()
    early_count = (df_all['exit_reason'] == 'early_exit').sum()
    
    print("\n--- EXIT REASON BREAKDOWN ---")
    print(f"TP (Target):  {tp_count}")
    print(f"SL (Stop):    {sl_count}")
    print(f"EOD (Close):   {eod_count}")
    print(f"Early Exit:   {early_count}")
    
    avg_tp_r = df_all[df_all['exit_reason'] == 'target']['outcome_R'].mean()
    avg_sl_r = df_all[df_all['exit_reason'] == 'stop']['outcome_R'].mean()
    
    print(f"\nAvg R on TP:  {avg_tp_r:.2f}")
    print(f"Avg R on SL:  {avg_sl_r:.2f}")

import asyncio
import pandas as pd
import os
from datetime import datetime, timedelta
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest

def run_pipeline_for_day(date_str: str) -> list:
    """Runs the full L3 pipeline for a single trading day."""
    print(f"\n📅 --- PROCESSING DATE: {date_str} ---")
    
    symbol = "NQ.FUT"
    # standard NY session hours
    start = f"{date_str}T14:30:00"
    end = f"{date_str}T21:00:00"

    # 1. Fetch MBO Data
    try:
        mbo_df = fetch_mbo_data(symbol, start, end)
        if mbo_df.empty:
            print(f"⚠️ No data for {date_str}. Skipping.")
            return []
    except Exception as e:
        print(f"❌ Fetch failed for {date_str}: {e}")
        return []

    # 2. Build L3 Order Book
    events = process_mbo_stream(mbo_df)
    if not events:
        print(f"⚠️ No events generated for {date_str}. Skipping.")
        return []
    events_df = pd.DataFrame(events)

    # 3. Intelligence Layer
    features = extract_l3_features(mbo_df, events_df)
    features = compute_context(features)
    features = compute_sequence(features)
    features = score_events(features)
    features = apply_decision_rules(features)

    # 4. Backtest
    result = run_l3_backtest(features)
    trades = result.get("trades", [])
    
    print(f"✅ {date_str} Complete: {len(trades)} trades generated.")
    
    # Format for ML
    ml_trades = []
    for t in trades:
        if t["result"] not in ["win", "loss"]: continue
        
        row_data = {
            "timestamp_utc": t["ts"],
            "direction": t["direction"],
            "result": t["result"],
            "outcome_r": t["outcome_R"],
            "target_is_good_setup": 1 if t["result"] == "win" else 0,
        }
        if "features" in t and isinstance(t["features"], dict):
            for k, v in t["features"].items():
                if k not in ["ts", "price", "symbol", "index", "action", "order_id"]:
                    row_data[k] = v
        ml_trades.append(row_data)
        
    return ml_trades

def main():
    print("🚀 Starting MULTI-DAY L3 Order Flow Pipeline...")

    # Define date range
    # Example: First week of Jan 2023
    start_date = datetime(2023, 1, 3)
    end_date = datetime(2023, 1, 10)
    
    current_date = start_date
    all_ml_data = []
    total_trades = 0

    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() < 5:
            date_str = current_date.strftime("%Y-%m-%d")
            day_trades = run_pipeline_for_day(date_str)
            
            if day_trades:
                all_ml_data.extend(day_trades)
                total_trades += len(day_trades)
                print(f"📈 Cumulative Trades: {total_trades}")
        
        current_date += timedelta(days=1)

    # 5. Save/Update Master ML Dataset
    if all_ml_data:
        os.makedirs("orderflow_ml", exist_ok=True)
        new_df = pd.DataFrame(all_ml_data)
        out_path = "orderflow_ml/ml_dataset.csv"
        
        if os.path.exists(out_path):
            existing_df = pd.read_csv(out_path)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # Prevent duplicates by timestamp and direction
            combined_df.drop_duplicates(subset=["timestamp_utc", "direction"], inplace=True)
            combined_df.to_csv(out_path, index=False)
            print(f"\n✅ Master Dataset UPDATED: {out_path} (Total: {len(combined_df)} trades)")
        else:
            new_df.to_csv(out_path, index=False)
            print(f"\n✅ Master Dataset CREATED: {out_path} (Total: {len(new_df)} trades)")
    else:
        print("\n❌ No trades generated across the specified range.")

if __name__ == "__main__":
    main()

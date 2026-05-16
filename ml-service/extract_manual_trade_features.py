import json
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

# Configuration
TRADES_FILE = "/Users/asal/Desktop/own/machine learning/my.trades.json"
MBO_DIR = "data/raw/mbo/NQ"
OUTPUT_FILE = "orderflow_ml/manual_trade_dataset.csv"
WARMUP_WINDOW_MINUTES = 10  # Minutes of data to process before the first trade of the day (or per trade if session is too big)

def robust_json_load(filepath):
    import json
    with open(filepath, 'r') as f:
        data = f.read()
    
    decoder = json.JSONDecoder()
    pos = 0
    results = []
    while pos < len(data):
        # Skip whitespace/junk
        while pos < len(data) and (data[pos].isspace() or data[pos] in [',', '\n', '\r']):
            pos += 1
        if pos >= len(data):
            break
        try:
            obj, pos = decoder.raw_decode(data, pos)
            if isinstance(obj, list):
                results.extend(obj)
            else:
                results.append(obj)
        except json.JSONDecodeError:
            # Move forward until we find a potential start of a JSON object/array
            pos += 1
    return results

def extract_manual_features():
    print("🚀 Starting Discretionary Trade L3 Feature Extraction...")
    
    # 1. Load my.trades.json
    if not os.path.exists(TRADES_FILE):
        print(f"❌ Error: {TRADES_FILE} not found.")
        return

    try:
        trades_raw = robust_json_load(TRADES_FILE)
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}")
        return

    if not isinstance(trades_raw, list):
        print("❌ Error: Expected JSON array of trades.")
        return

    # 2. Parse and Clean Trades
    processed_trades = []
    for t in trades_raw:
        try:
            # Parse UTC timestamp
            utc_ts = pd.to_datetime(t.get("utcDatetime")).tz_convert('UTC')
            
            processed_trades.append({
                "trade_id": t.get("id"),
                "timestamp_utc": utc_ts,
                "date": utc_ts.strftime('%Y-%m-%d'),
                "direction": t.get("direction"),
                "entry_price": t.get("entryPrice"),
                "outcome_r": t.get("outcomeR"),
                "result": t.get("result"),
                "description": t.get("description", ""),
                "reasons": "|".join(t.get("reasons", []))
            })
        except Exception as e:
            print(f"⚠️ Skipping trade {t.get('id')} due to parsing error: {e}")

    df_manual = pd.DataFrame(processed_trades)
    print(f"✅ Loaded {len(df_manual)} manual trades.")

    # 3. Group by Date and Process
    final_dataset = []
    dates = df_manual["date"].unique()
    
    for date_str in sorted(dates):
        mbo_path = os.path.join(MBO_DIR, f"{date_str}.parquet")
        if not os.path.exists(mbo_path):
            print(f"⚠️ Skipping {date_str}: MBO file not found.")
            continue
            
        print(f"📅 Processing Date: {date_str}")
        try:
            # Load MBO data for the day
            mbo_df = pd.read_parquet(mbo_path)
            if mbo_df.empty:
                print(f"⚠️ {date_str} MBO data is empty. Skipping.")
                continue
                
            # Filter for trades on this date
            day_trades = df_manual[df_manual["date"] == date_str].copy()
            day_trades = day_trades.sort_values("timestamp_utc")
            
            # Find the time range for the day's trades to optimize processing
            min_ts = day_trades["timestamp_utc"].min() - timedelta(minutes=WARMUP_WINDOW_MINUTES)
            max_ts = day_trades["timestamp_utc"].max() + timedelta(minutes=1)
            
            # Slice MBO data to relevant window
            mbo_slice = mbo_df.loc[min_ts:max_ts]
            if mbo_slice.empty:
                print(f"⚠️ No MBO data in window {min_ts} to {max_ts} for {date_str}. Skipping.")
                continue
            
            print(f"   - Processing {len(mbo_slice)} MBO rows for window...")
            
            # Reconstruct Order Book and generate events
            events = process_mbo_stream(mbo_slice)
            if not events:
                print(f"⚠️ No events generated for {date_str}. Skipping.")
                continue
                
            events_df = pd.DataFrame(events)
            # Ensure ts is datetime and sorted for merge_asof
            events_df["ts"] = pd.to_datetime(events_df["ts"], utc=True).dt.as_unit('ns')
            events_df = events_df.sort_values("ts")
            
            # Extract L3 Features
            features_df = extract_l3_features(mbo_slice, events_df)
            if features_df.empty:
                print(f"⚠️ Feature extraction returned empty for {date_str}. Skipping.")
                continue
            
            # Ensure feature ts is datetime for merge_asof
            features_df["ts"] = pd.to_datetime(features_df["ts"], utc=True).dt.as_unit('ns')
            features_df = features_df.sort_values("ts")
            
            # Normalize manual trade timestamps for merging
            day_trades["timestamp_utc"] = pd.to_datetime(day_trades["timestamp_utc"], utc=True).dt.as_unit('ns')
            
            # Join manual trades with features using merge_asof
            merged = pd.merge_asof(
                day_trades,
                features_df,
                left_on="timestamp_utc",
                right_on="ts",
                direction="backward",
                tolerance=pd.Timedelta("30s") # Loosened tolerance for manual trades
            )
            
            # Count how many matched
            matched = merged["ts"].notnull().sum()
            print(f"   - Matched {matched}/{len(day_trades)} trades with orderflow features.")
            
            final_dataset.append(merged[merged["ts"].notnull()])
            
        except Exception as e:
            print(f"❌ Error processing {date_str}: {e}")
            import traceback
            traceback.print_exc()

    if not final_dataset:
        print("❌ No trades were successfully matched with features.")
        return

    # 4. Consolidate and Save
    full_df = pd.concat(final_dataset, ignore_index=True)
    
    # Cleaning
    # Drop intermediate columns
    full_df = full_df.drop(columns=["date", "ts"])
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    full_df.to_csv(OUTPUT_FILE, index=False)
    
    print("\n" + "="*40)
    print("✅ EXTRACTION COMPLETE")
    print("="*40)
    print(f"Total Trades Analyzed: {len(df_manual)}")
    print(f"Total Trades with Features: {len(full_df)}")
    print(f"Dataset Saved to: {OUTPUT_FILE}")
    print("="*40)

if __name__ == "__main__":
    extract_manual_features()

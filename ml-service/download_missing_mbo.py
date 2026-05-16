import os
import databento as db
import pandas as pd
from datetime import datetime
import time
import sys

# Import existing configuration
try:
    from app.data.databento_client import DATABENTO_API_KEY, get_mbo_cache_path
except ImportError:
    # Fallback if import fails
    DATABENTO_API_KEY = os.getenv("DATABENTO_API_KEY", "")
    def get_mbo_cache_path(symbol, date_str):
        clean_symbol = symbol.split('.')[0]
        directory = f"data/raw/mbo/{clean_symbol}"
        os.makedirs(directory, exist_ok=True)
        return f"{directory}/{date_str}.parquet"

# Dates requested for the manual edge model
DEFAULT_TARGET_DATES = [
    "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-08",
    "2026-05-12", "2026-05-13", "2026-05-14"
]

SYMBOL = "NQ.FUT"
# Broad window to capture pre-market discretionary trades (London Open to NY Close)
START_TIME = "08:00:00" 
END_TIME = "21:00:00"   

def download_missing_mbo(dates=None):
    if dates is None:
        dates = DEFAULT_TARGET_DATES
        
    print(f"🚀 Starting Databento MBO Download Pipeline for {len(dates)} dates...")
    
    # Prioritize environment variable over hardcoded key
    api_key = os.getenv("DATABENTO_API_KEY", DATABENTO_API_KEY)
    
    if not api_key:
        print("❌ Error: No Databento API Key found. Please set the DATABENTO_API_KEY environment variable.")
        return

    client = db.Historical(api_key)
    summary = {"downloaded": 0, "skipped": 0, "failed": 0}
    
    for date_str in dates:
        cache_path = get_mbo_cache_path(SYMBOL, date_str)
        
        if os.path.exists(cache_path):
            print(f"⏩ {date_str} already exists in cache. Skipping.")
            summary["skipped"] += 1
            continue
            
        print(f"📥 Fetching {SYMBOL} for {date_str} ({START_TIME} to {END_TIME} UTC)...")
        
        # Databento expects ISO8601 timestamps
        start = f"{date_str}T{START_TIME}Z"
        end = f"{date_str}T{END_TIME}Z"
        
        retries = 2
        while retries >= 0:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                
                # Fetch data
                data = client.timeseries.get_range(
                    dataset="GLBX.MDP3",
                    schema="mbo",
                    symbols=[SYMBOL],
                    stype_in="parent",
                    start=start,
                    end=end,
                )
                
                df = data.to_df()
                if df.empty:
                    print(f"⚠️ No data returned for {date_str}. This might be a weekend or holiday.")
                    summary["failed"] += 1
                    break
                    
                # Save as parquet
                df.to_parquet(cache_path)
                print(f"✅ Successfully downloaded and saved {date_str} ({len(df)} rows)")
                summary["downloaded"] += 1
                break
                
            except Exception as e:
                if "401" in str(e) or "authentication" in str(e).lower():
                    print(f"❌ Authentication Failed: Your API key appears invalid or unauthorized.")
                    summary["failed"] += 1
                    return # Exit early on auth failure
                
                if retries > 0:
                    print(f"⚠️ Error downloading {date_str}: {e}")
                    print(f"🔄 Retrying in 5 seconds... ({retries} retries left)")
                    time.sleep(5)
                    retries -= 1
                else:
                    print(f"❌ Failed to download {date_str} after multiple attempts: {e}")
                    summary["failed"] += 1
                    break

    print("\n" + "="*40)
    print("🏁 DOWNLOAD SUMMARY")
    print("="*40)
    print(f"Downloaded : {summary['downloaded']}")
    print(f"Skipped    : {summary['skipped']}")
    print(f"Failed     : {summary['failed']}")
    print("="*40)
    
    if summary["failed"] > 0:
        print("💡 Tip: Verify your DATABENTO_API_KEY and account balance at databento.com")

if __name__ == "__main__":
    # Allow passing dates as CLI arguments: python download_missing_mbo.py 2026-05-15 2026-05-16
    cli_dates = sys.argv[1:] if len(sys.argv) > 1 else None
    download_missing_mbo(cli_dates)

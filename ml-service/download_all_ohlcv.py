import os
import sys
import pandas as pd
import subprocess
import time

def main():
    # Set symbol and API key from environment
    SYMBOL = os.environ.get("TARGET_SYMBOL", "GC.FUT")
    API_KEY = os.environ.get("DATABENTO_API_KEY")
    
    if not API_KEY:
        print("❌ Error: DATABENTO_API_KEY environment variable is not set.")
        sys.exit(1)
        
    print(f"🚀 Starting full 2024-2025 OHLCV Download for {SYMBOL}...")
    
    # Generate all dates for 2024 and 2025
    dates = pd.date_range(start='2024-01-01', end='2025-12-31').strftime('%Y-%m-%d').tolist()
    total_dates = len(dates)
    print(f"Total dates to process: {total_dates}")
    
    # Process in chunks of 15 days to avoid passing too many arguments to sys.argv
    chunk_size = 15
    for i in range(0, total_dates, chunk_size):
        chunk = dates[i:i+chunk_size]
        chunk_str = " ".join(chunk)
        print(f"\n📦 Processing chunk {i//chunk_size + 1}/{(total_dates + chunk_size - 1)//chunk_size} ({chunk[0]} to {chunk[-1]})...")
        
        # Call the existing download_ohlcv.py script as a subprocess
        cmd = ["python3", "download_ohlcv.py"] + chunk
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Error running chunk: {e}")
            
        # Small sleep to respect rate limits / server load
        time.sleep(1)

    print("\n🏁 Finished downloading all 2024-2025 OHLCV data!")

if __name__ == "__main__":
    main()

import pandas as pd
import os
import glob

print("--- DATA DIRECTORY DIAGNOSTICS ---")
files = glob.glob("data/*.parquet")
if not files:
    print("No parquet files found in data/")
else:
    for f in files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        try:
            df = pd.read_parquet(f)
            if df.empty:
                print(f"File: {f} | Size: {size_mb:.2f}MB | Status: EMPTY")
            else:
                # Get index range
                start = df.index[0]
                end = df.index[-1]
                print(f"File: {f} | Size: {size_mb:.2f}MB | Range: {start} to {end}")
                if 'action' in df.columns:
                    print(f"  Actions found: {df['action'].unique()}")
        except Exception as e:
            print(f"File: {f} | Error reading: {e}")
print("----------------------------------")

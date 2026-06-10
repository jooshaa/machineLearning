import os
import subprocess
import pandas as pd
import time
import glob
from download_missing_mbo import download_missing_mbo

def run_pipeline():
    # 1. Define 2024 months (Resuming from March)
    months = [
        ("2024-03-01", "2024-03-31"),
        ("2024-04-01", "2024-04-30"),
        ("2024-05-01", "2024-05-31"),
        ("2024-06-01", "2024-06-30"),
    ]
    
    SYMBOL = os.getenv("TARGET_SYMBOL", "NQ.FUT")
    clean_symbol = SYMBOL.split('.')[0]
    
    # Path for the master 2024 dataset
    master_csv = f"orderflow_ml/volume_delta_dataset_{clean_symbol}_2024.csv"
    temp_csv = f"orderflow_ml/volume_delta_dataset_{clean_symbol}.csv"
    
    print(f"⚠️ Initial disk cleanup to ensure safe start...")
    for f in glob.glob(f"data/raw/mbo/{clean_symbol}/*.parquet") + glob.glob(f"data/raw/mbo/{clean_symbol}/*.holiday"):
        os.remove(f)

    for start_date, end_date in months:
        print(f"\n{'='*50}")
        print(f"🚀 STARTING PIPELINE CHUNK: {start_date} to {end_date}")
        print(f"{'='*50}\n")
        
        # 1. Generate weekdays for the month
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        
        # 2. Download MBO Data
        print(f"📥 Downloading {len(date_strs)} days...")
        try:
            download_missing_mbo(dates=date_strs)
        except Exception as e:
            print(f"❌ Failed to download chunk {start_date}: {e}")
            break
            
        # 3. Run Strategy
        print(f"\n⚙️ Running backtest strategy...")
        # Call the script using subprocess so it runs fresh
        try:
            subprocess.run(["python3", "strategy_volume_delta.py"], check=True)
        except subprocess.CalledProcessError:
            print(f"❌ Strategy script failed for chunk {start_date}. Stopping pipeline.")
            break
        
        # 4. Append generated signals to master CSV
        if os.path.exists(temp_csv):
            print(f"💾 Merging {temp_csv} into {master_csv}...")
            df_new = pd.read_csv(temp_csv)
            if os.path.exists(master_csv):
                df_master = pd.read_csv(master_csv)
                df_combined = pd.concat([df_master, df_new]).drop_duplicates(subset=['entry_time'])
            else:
                df_combined = df_new.drop_duplicates(subset=['entry_time'])
            
            # Sort chronologically
            df_combined = df_combined.sort_values('entry_time')
            df_combined.to_csv(master_csv, index=False)
            print(f"✅ Master CSV now has {len(df_combined)} signals.")
        else:
            print(f"⚠️ Warning: No {temp_csv} found for this month.")

        # 5. Cleanup Parquet files to free disk space!
        print("🗑️ Cleaning up .parquet files to free 10GB of disk space...")
        deleted_count = 0
        for f in glob.glob(f"data/raw/mbo/{clean_symbol}/*.parquet") + glob.glob(f"data/raw/mbo/{clean_symbol}/*.holiday"):
            os.remove(f)
            deleted_count += 1
        print(f"🧹 Deleted {deleted_count} large files.")
        
        print(f"✅ Finished chunk {start_date} - {end_date}\n")
        time.sleep(5) # Small pause before next month

if __name__ == "__main__":
    run_pipeline()

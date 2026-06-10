import databento as db
import os, sys
import time

api_key = os.environ.get("DATABENTO_API_KEY")
client = db.Historical(api_key)

SYMBOL = os.environ.get("TARGET_SYMBOL", "NQ.FUT")
clean_symbol = SYMBOL.split('.')[0].upper()

dates = sys.argv[1:] if len(sys.argv) > 1 else []
for date in dates:
    out_path = f"data/raw/ohlcv/{clean_symbol}/{date}.parquet"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        print(f"⏩ {date} already exists in cache. Skipping.")
        continue

    retries = 3
    for attempt in range(retries):
        temp_dbn = os.path.join(os.path.dirname(out_path), f"temp_ohlcv_{date}.dbn")
        try:
            # Use path= to stream to disk (fixes latin-1 encoding issue)
            data = client.timeseries.get_range(
                dataset="GLBX.MDP3",
                schema="ohlcv-1m",
                symbols=[SYMBOL],
                stype_in="parent",
                start=f"{date}T08:00:00Z",
                end=f"{date}T21:00:00Z",
                path=temp_dbn,
            )
            df = data.to_df()
            if df.empty:
                print(f"⚠️ No OHLCV data for {date} (holiday/weekend).")
                break
            df.to_parquet(out_path)
            print(f"✅ Saved {clean_symbol} OHLCV {date} ({len(df)} rows)")
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"⚠️ Error downloading {date}: {e}. Retrying in 3 seconds...")
                time.sleep(3)
            else:
                print(f"❌ Failed to download OHLCV for {date} after {retries} attempts: {e}")
        finally:
            if os.path.exists(temp_dbn):
                os.remove(temp_dbn)

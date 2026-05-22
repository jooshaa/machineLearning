import databento as db
import os, sys
from datetime import datetime, timedelta

api_key = os.environ.get("DATABENTO_API_KEY")
client = db.Historical(api_key)

dates = sys.argv[1:] if len(sys.argv) > 1 else []
for date in dates:
    out_path = f"data/raw/ohlcv/NQ/{date}.parquet"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        data = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            schema="ohlcv-1m",
            symbols=["NQ.FUT"],
            stype_in="parent",
            start=f"{date}T08:00:00Z",
            end=f"{date}T21:00:00Z",
        )
        df = data.to_df()
        df.to_parquet(out_path)
        print(f"✅ Saved {date} ({len(df)} rows)")
    except Exception as e:
        print(f"❌ Failed to download OHLCV for {date}: {e}")

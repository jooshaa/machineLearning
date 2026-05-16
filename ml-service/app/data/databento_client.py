import os
import databento as db
import pandas as pd
from datetime import datetime

# API Key: db-b6FgEtR4EgGNYYyyW8LWUnMEVkYuk
DATABENTO_API_KEY = os.getenv("DATABENTO_API_KEY")

def get_mbo_cache_path(symbol: str, date_str: str) -> str:
    """Helper to get cache path: data/raw/mbo/{symbol}/{date}.parquet"""
    # Clean symbol for filename (e.g. NQ.FUT -> NQ)
    clean_symbol = symbol.split('.')[0]
    directory = f"data/raw/mbo/{clean_symbol}"
    os.makedirs(directory, exist_ok=True)
    return f"{directory}/{date_str}.parquet"

def fetch_mbo_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetches Level 3 MBO data with local caching.
    Supports symbols like NQ.FUT, ES.FUT.
    """
    client = db.Historical(DATABENTO_API_KEY)
    
    # 1. Determine date for caching (use start date)
    start_dt = datetime.fromisoformat(start.replace('Z', ''))
    date_str = start_dt.strftime('%Y-%m-%d')
    cache_path = get_mbo_cache_path(symbol, date_str)
    
    # 2. Check Cache
    if os.path.exists(cache_path):
        print(f"📦 Loaded from cache: {cache_path}")
        return pd.read_parquet(cache_path)
    
    # 3. Fetch from Databento
    print(f"📥 Fetching from Databento: {symbol} for {date_str}...")
    try:
        data = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            schema="mbo",
            symbols=[symbol],
            stype_in="parent",
            start=start,
            end=end,
        )
        df = data.to_df()
        
        # 4. Debug inspection
        print(f"📊 MBO Data Sample:\n{df.head(3)}")
        print(f"📋 Columns: {df.columns.tolist()}")
        
        # 5. Save to Cache
        df.to_parquet(cache_path)
        print(f"✅ Saved to cache: {cache_path}")
        return df
    except Exception as e:
        print(f"❌ Databento fetch error: {e}")
        raise e

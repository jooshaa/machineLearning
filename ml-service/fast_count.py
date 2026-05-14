import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

dates = ["2025-01-13", "2025-01-22", "2025-02-19", "2025-03-05"]
symbol = "NQ.FUT"

for d in dates:
    start = f"{d}T14:30:00"
    end = f"{d}T21:00:00"
    mbo_df = fetch_mbo_data(symbol, start, end)
    events = process_mbo_stream(mbo_df)
    events_df = pd.DataFrame(events)
    features = extract_l3_features(mbo_df, events_df)
    
    # Calculate tradable spoof entries
    is_ny = (pd.to_datetime('09:30').time() <= features['ts'].dt.tz_convert('US/Eastern').dt.time) & \
            (features['ts'].dt.tz_convert('US/Eastern').dt.time < pd.to_datetime('16:00').time())
    
    min_contracts = is_ny.apply(lambda x: 30 if x else 20)
    is_tradable = features['size'] >= min_contracts
    
    spoof_trades = ((features['event_type'] == 'spoof') & is_tradable).sum()
    
    # Calculate boundary setups
    setups = features['event_type'].isin(["absorption", "trap", "breakout"]).sum()
    
    print(f"--- Date: {d} ---")
    print(f"Количество сделок (примерно): {spoof_trades}")
    print(f"Сетапов на VAH/VAL (passed_boundary): {setups}")
    print(f"Первых импульсов (blocked_aggression): 0")
    print(f"Ретестов (passed_aggression): 0")


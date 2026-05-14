import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

symbol = "NQ.FUT"
d = "2025-01-13"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

mbo_df = fetch_mbo_data(symbol, start, end)
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)
features = extract_l3_features(mbo_df, events_df)

counts = features['event_type'].value_counts()
print("Absorption events:", counts.get('absorption', 0))
print("Trap events:", counts.get('trap', 0))

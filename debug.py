import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

symbol = "NQ.FUT"
start = "2023-01-05T14:30:00"
end = "2023-01-05T15:30:00"
mbo_df = fetch_mbo_data(symbol, start, end)
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)
features = extract_l3_features(mbo_df, events_df)

print("Unique event_types:", features['event_type'].unique())
print("Value counts:")
print(features['event_type'].value_counts())

import pandas as pd
import json
import warnings
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream

warnings.filterwarnings('ignore')

d = "2025-03-05"
symbol = "NQ.FUT"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

mbo_df = fetch_mbo_data(symbol, start, end)
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)

print("Min TS:", events_df['ts'].min())
print("Max TS:", events_df['ts'].max())
print("Number of events:", len(events_df))


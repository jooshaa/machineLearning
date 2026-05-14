import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
import warnings

warnings.filterwarnings('ignore')

d = "2025-03-05"
symbol = "NQ.FUT"
start = f"{d}T14:30:00"
end = f"{d}T21:00:00"

mbo_df = fetch_mbo_data(symbol, start, end)
events = process_mbo_stream(mbo_df)
events_df = pd.DataFrame(events)

print("Min price:", events_df["price"].min())
print("Max price:", events_df["price"].max())

bad_prices = events_df[events_df["price"] < 10000]
print(f"Number of prices < 10000: {len(bad_prices)}")
if len(bad_prices) > 0:
    print(bad_prices.head())

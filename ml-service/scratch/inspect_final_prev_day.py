
import pandas as pd
try:
    prev_df = pd.read_parquet("data/raw/mbo/NQ/2025-01-08.parquet")

    ny_prev = prev_df[
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time >= 
         pd.to_datetime("09:30").time()) &
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time < 
         pd.to_datetime("16:00").time())
    ]

    clean = ny_prev[
        (ny_prev["price"] > 18000) & 
        (ny_prev["price"] < 25000) &
        (~ny_prev["symbol"].str.contains("-", na=False))
    ]

    # Медиана и IQR фильтр (1% и 99% квантили)
    median = clean["price"].median()
    q1 = clean["price"].quantile(0.01)
    q99 = clean["price"].quantile(0.99)

    final = clean[(clean["price"] >= q1) & (clean["price"] <= q99)]

    print(f"Строк финал: {len(final)}")
    if not final.empty:
        print(f"Диапазон: {final['price'].min():.2f} - {final['price'].max():.2f}")
        print(f"Медиана: {median:.2f}")
    else:
        print("После фильтрации данных не осталось.")
except Exception as e:
    print(f"Error: {e}")

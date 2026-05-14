
import pandas as pd
try:
    prev_df = pd.read_parquet("data/raw/mbo/NQ/2025-01-08.parquet")

    # Фильтр NY сессии предыдущего дня
    # Note: raw data uses ts_event
    ny_prev = prev_df[
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time >= 
         pd.to_datetime("09:30").time()) &
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time < 
         pd.to_datetime("16:00").time())
    ]

    print(f"Строк NY предыдущего дня: {len(ny_prev)}")
    if not ny_prev.empty:
        print(f"Диапазон цен: {ny_prev['price'].min():.2f} - {ny_prev['price'].max():.2f}")
        print(f"Медиана цены: {ny_prev['price'].median():.2f}")
    else:
        print("NY сессия пуста.")
except Exception as e:
    print(f"Error: {e}")


import pandas as pd
try:
    prev_df = pd.read_parquet("data/raw/mbo/NQ/2025-01-08.parquet")

    ny_prev = prev_df[
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time >= 
         pd.to_datetime("09:30").time()) &
        (prev_df["ts_event"].dt.tz_convert("US/Eastern").dt.time < 
         pd.to_datetime("16:00").time())
    ]

    # Фильтр аномалий — только реальные NQ цены
    clean = ny_prev[
        (ny_prev["price"] > 18000) & 
        (ny_prev["price"] < 25000) &
        (~ny_prev["symbol"].str.contains("-", na=False))
    ]

    print(f"Строк после очистки: {len(clean)}")
    if not clean.empty:
        print(f"Диапазон цен: {clean['price'].min():.2f} - {clean['price'].max():.2f}")
        print(f"Медиана: {clean['price'].median():.2f}")
    else:
        print("После очистки данных не осталось.")
except Exception as e:
    print(f"Error: {e}")

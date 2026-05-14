
import pandas as pd
try:
    df = pd.read_parquet("data/raw/mbo/NQ/2025-01-20.parquet")
    ts_col = "ts_event" if "ts_event" in df.columns else "ts"
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)

    # NY сессия
    ny = df[
        (df[ts_col].dt.tz_convert("US/Eastern").dt.time >= pd.to_datetime("09:30").time()) &
        (df[ts_col].dt.tz_convert("US/Eastern").dt.time < pd.to_datetime("16:00").time())
    ]

    # Фильтр аномалий
    q1 = ny["price"].quantile(0.01)
    q99 = ny["price"].quantile(0.99)
    clean = ny[(ny["price"] >= q1) & (ny["price"] <= q99)]

    print(f"Строк после очистки: {len(clean)}")
    if not clean.empty:
        print(f"Диапазон цен: {clean['price'].min():.2f} - {clean['price'].max():.2f}")
        print(f"Медиана: {clean['price'].median():.2f}")
    else:
        print("После очистки данных не осталось.")
except Exception as e:
    print(f"Error: {e}")

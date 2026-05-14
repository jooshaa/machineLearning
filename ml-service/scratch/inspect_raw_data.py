
import pandas as pd
try:
    df = pd.read_parquet("data/raw/mbo/NQ/2025-01-13.parquet")
    ny_df = df[df["session"] == "NY"] if "session" in df.columns else pd.DataFrame()
    print(f"Всего строк: {len(df)}")
    print(f"NY строк: {len(ny_df)}")
    print(f"Сессии в данных: {df['session'].unique() if 'session' in df.columns else 'Нет колонки session'}")
    if not ny_df.empty:
        print(f"Диапазон цен NY: {ny_df['price'].min():.2f} - {ny_df['price'].max():.2f}")
    print(f"Диапазон дат: {df['ts'].min()} - {df['ts'].max()}")
except Exception as e:
    print(f"Error: {e}")

import pandas as pd
import glob

files = glob.glob("data/raw/mbo/NQ/2023-01-05.parquet")
if not files:
    print("CRITICAL: File 2023-01-05.parquet not found!")
else:
    f = files[0]
    print(f"Inspecting file: {f}")
    df = pd.read_parquet(f)
    print(f"Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    print("\nFirst 5 rows:")
    print(df.head(5))
    if 'action' in df.columns:
        print(f"\nUnique actions: {df['action'].unique()}")
    else:
        print("\nColumn 'action' NOT FOUND!")
    
    # Check for trades
    trades = df[df['action'].isin(['T', 'F', 'V', 't', 'f', 'v'])]
    print(f"\nPotential trades found: {len(trades)}")

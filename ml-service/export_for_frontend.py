import pandas as pd
import json
import os

def export():
    csv_path = "orderflow_ml/volume_delta_dataset.csv"
    json_path = "../frontend/public/volume_delta_trades.json"
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    
    trades = []
    for _, row in df.iterrows():
        trades.append({
            "time": str(row['entry_time']),
            "dir": "Long" if row['direction'] == "buy" else "Short",
            "entry": float(row['entry_price']),
            "result": "win" if row['outcome'] == "win" else "loss" if row['outcome'] == "loss" else "breakeven",
            "tp": float(row['tp_price']),
            "sl": float(row['sl_price']),
            "score": int(row['score']),
            "r": float(row['r_multiple'])
        })
        
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w') as f:
        json.dump(trades, f, indent=2)
        
    print(f"✅ Exported {len(trades)} trades to {json_path}")

if __name__ == "__main__":
    export()

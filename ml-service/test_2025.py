"""
Out-of-sample test: 2024-trained model evaluated on 2025 GC signals.
Run strategy first:
  TARGET_SYMBOL=GC.FUT START_DATE=2025-01-01 END_DATE=2025-12-31 python3 strategy_volume_delta.py
Then:
  python3 test_2025.py
"""
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, classification_report

SYMBOL     = os.getenv("TARGET_SYMBOL", "GC.FUT")
clean      = SYMBOL.split('.')[0]
CSV_PATH   = f"orderflow_ml/volume_delta_dataset_{clean}.csv"
MODEL_PATH = f"models/volume_delta_xgb_{SYMBOL}.pkl"

# Load model first so we know exactly which features it expects
print(f"Loading model: {MODEL_PATH}")
saved  = joblib.load(MODEL_PATH)
model  = saved['model'] if isinstance(saved, dict) else saved
features = saved['features'] if isinstance(saved, dict) and 'features' in saved else None

print(f"Loading signals: {CSV_PATH}")
df = pd.read_csv(CSV_PATH)
df = df[df['outcome'] != 'timeout'].copy()

df['entry_dt']    = pd.to_datetime(df['entry_time'].str.replace('Z', ''), errors='coerce')
df['hour']        = df['entry_dt'].dt.hour
df['day_of_week'] = df['entry_dt'].dt.dayofweek
df = df.sort_values('entry_dt').reset_index(drop=True)

if 'absorption' in df.columns:
    df['absorption'] = df['absorption'].astype(int)

df['target'] = (df['outcome'] == 'win').astype(int)

# Fill any feature the model expects but the new CSV doesn't have
for f in (features or []):
    if f not in df.columns:
        df[f] = 0.0

X = df[features].fillna(0.0)
y = df['target']

y_pred  = model.predict(X)
y_proba = model.predict_proba(X)[:, 1]

print(f"\nSignals: {len(df)}  ({df['entry_dt'].min().date()} → {df['entry_dt'].max().date()})")
print(f"Raw WR: {y.mean():.1%}")

print("\n" + "="*50)
print("2025 OUT-OF-SAMPLE RESULTS (2024 model)")
print("="*50)
print(f"Accuracy:  {accuracy_score(y, y_pred):.3f}")
print(f"Precision: {precision_score(y, y_pred, zero_division=0):.3f}")
print(f"Recall:    {recall_score(y, y_pred, zero_division=0):.3f}")
print()
print(classification_report(y, y_pred, target_names=['loss', 'win'], zero_division=0))

print("="*50)
print("CONFIDENCE BUCKETS")
print("="*50)
df['proba'] = y_proba

for lo, hi in [(0.0, 0.4), (0.4, 0.6), (0.6, 0.75), (0.75, 1.01)]:
    bucket = df[(df['proba'] >= lo) & (df['proba'] < hi)]
    if len(bucket) == 0:
        continue
    wr = bucket['target'].mean()
    print(f"  {lo:.0%}–{hi:.0%} confidence: {len(bucket):3d} signals → WR {wr:.1%}")

if 'r_multiple' in df.columns:
    high_conf = df[df['proba'] >= 0.75]
    if len(high_conf) > 0:
        print(f"\nHigh-confidence (>75%) avg R: {high_conf['r_multiple'].mean():.2f}")

print("\nIf WR rises with confidence → edge holds in 2025.")

"""
Chronological train/test split within 2024.
Train: Jan–Sep 2024  |  Test: Oct–Dec 2024
Shows whether the model predicts unseen data correctly.
"""
import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, classification_report

SYMBOL   = os.getenv("TARGET_SYMBOL", "GC.FUT")
clean    = SYMBOL.split('.')[0]
CSV_PATH = f"orderflow_ml/volume_delta_dataset_{clean}_2024.csv"

TRAIN_FEATURES = [
    'hour', 'day_of_week',
    'impulse_points', 'impulse_speed', 'impulse_cvd',
    'zone_position', 'zone_delta_pct', 'zone_volume',
    'touch_cvd_slope', 'touch_bid_stack', 'touch_ask_stack',
    'touch_ob_imbalance', 'touch_absorption', 'touch_spoof_count',
    'absorption', 'session', 'volatility', 'trend',
]

df = pd.read_csv(CSV_PATH)
df = df[df['outcome'] != 'timeout'].copy()

df['entry_dt'] = pd.to_datetime(df['entry_time'].str.replace('Z',''), errors='coerce')
df['hour']        = df['entry_dt'].dt.hour
df['day_of_week'] = df['entry_dt'].dt.dayofweek
df = df.sort_values('entry_dt').reset_index(drop=True)

for col in ['absorption', 'ob_large_limit', 'ob_layering']:
    if col in df.columns:
        df[col] = df[col].astype(int)

df['target'] = (df['outcome'] == 'win').astype(int)

available = [f for f in TRAIN_FEATURES if f in df.columns]
missing   = [f for f in TRAIN_FEATURES if f not in df.columns]
if missing:
    print(f"Missing features (zeros): {missing}")
    for f in missing:
        df[f] = 0.0

# Chronological split: first 75% = train, last 25% = test
split_idx = int(len(df) * 0.75)
train_df  = df.iloc[:split_idx]
test_df   = df.iloc[split_idx:]

print(f"Train: {len(train_df)} signals  ({train_df['entry_dt'].min().date()} → {train_df['entry_dt'].max().date()})")
print(f"Test:  {len(test_df)} signals  ({test_df['entry_dt'].min().date()} → {test_df['entry_dt'].max().date()})")
print(f"Train WR: {train_df['target'].mean():.1%}  |  Test WR: {test_df['target'].mean():.1%}")

X_train = train_df[available].fillna(0.0)
y_train = train_df['target']
X_test  = test_df[available].fillna(0.0)
y_test  = test_df['target']

model = XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric='logloss', random_state=42, n_jobs=-1,
)
model.fit(X_train, y_train)

y_pred  = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\n" + "="*45)
print("OUT-OF-SAMPLE RESULTS (Oct–Dec 2024)")
print("="*45)
print(f"Accuracy:  {accuracy_score(y_test, y_pred):.3f}")
print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.3f}")
print(f"Recall:    {recall_score(y_test, y_pred, zero_division=0):.3f}")
print()
print(classification_report(y_test, y_pred, target_names=['loss','win'], zero_division=0))

# Confidence buckets — the key question:
# When the model is confident (>70%), does it actually win?
print("="*45)
print("CONFIDENCE BUCKETS")
print("="*45)
test_df = test_df.copy()
test_df['proba'] = y_proba

for lo, hi in [(0.0, 0.4), (0.4, 0.6), (0.6, 0.75), (0.75, 1.01)]:
    bucket = test_df[(test_df['proba'] >= lo) & (test_df['proba'] < hi)]
    if len(bucket) == 0:
        continue
    wr = bucket['target'].mean()
    print(f"  Model confidence {lo:.0%}–{hi:.0%}: {len(bucket):3d} signals → actual WR {wr:.1%}")

print()
print("If WR rises with confidence → model has real predictive power.")

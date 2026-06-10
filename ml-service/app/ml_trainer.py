import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import cross_validate, StratifiedKFold
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

FEATURES = [
    'hour', 'day_of_week',
    'sl_distance', 'reward_risk',
    'score', 'absorption', 'exhaustion_score',
    'impulse_points', 'impulse_speed', 'impulse_cvd',
    'zone_position', 'zone_delta_pct', 'zone_volume',
    'ob_large_limit', 'ob_layering',
    'session', 'volatility', 'trend',
]

def train_model():
    SYMBOL = os.getenv("TARGET_SYMBOL", "NQ.FUT")
    clean_symbol = SYMBOL.split('.')[0]
    csv_path = os.path.join(parent_dir, "orderflow_ml", f"volume_delta_dataset_{clean_symbol}_2024.csv")

    if not os.path.exists(csv_path):
        return {"error": f"CSV not found at {csv_path}"}

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} total rows from CSV.")

    # Filter out timeouts
    df = df[df['outcome'] != 'timeout'].copy()
    print(f"After removing timeouts: {len(df)} rows.")

    if len(df) < 10:
        return {"error": "Not enough data to train (need at least 10 samples)."}

    # ── Time features ──
    df['entry_time_dt'] = pd.to_datetime(
        df['entry_time'].astype(str).str.replace('Z', ''), errors='coerce'
    )
    df['hour'] = df['entry_time_dt'].dt.hour
    df['day_of_week'] = df['entry_time_dt'].dt.dayofweek

    # ── Boolean to int ──
    for col in ['absorption', 'exhaustion', 'ob_large_limit', 'ob_layering']:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # ── Target ──
    df['target'] = (df['outcome'] == 'win').astype(int)

    # ── Only keep features that exist in the CSV ──
    available = [f for f in FEATURES if f in df.columns]
    missing   = [f for f in FEATURES if f not in df.columns]
    if missing:
        print(f"⚠️  Missing features (will be skipped): {missing}")

    X = df[available].copy()

    # ── Fill NaN with 0 — XGBoost handles NaN natively but be safe ──
    X = X.fillna(0.0)
    y = df['target']

    print("\nFeature description (verify non-zero values):")
    print(X.describe())
    print(f"\nClass balance  —  win: {y.sum()}  loss: {(y==0).sum()}")

    # ── XGBoost ──
    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(
        model, X, y, cv=cv,
        scoring=['accuracy', 'precision', 'recall'],
        error_score='raise'
    )

    acc  = float(cv_results['test_accuracy'].mean())
    prec = float(cv_results['test_precision'].mean())
    rec  = float(cv_results['test_recall'].mean())

    # Fit on all data for importances and saving
    model.fit(X, y)

    importances = model.feature_importances_
    feat_imp = {f: round(float(i), 4) for f, i in zip(available, importances)}
    feat_imp = dict(sorted(feat_imp.items(), key=lambda x: x[1], reverse=True))

    # Save model
    SYMBOL = os.getenv("TARGET_SYMBOL", "NQ.FUT")
    models_dir = os.path.join(parent_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f'volume_delta_xgb_{SYMBOL}.pkl')
    joblib.dump({'model': model, 'features': available}, model_path)

    print(f"\nAccuracy:  {acc:.2f}")
    print(f"Precision: {prec:.2f}")
    print(f"Recall:    {rec:.2f}")
    print(f"Feature Importances: {feat_imp}")
    print(f"Model saved → {model_path}")

    return {
        "accuracy":            round(acc,  2),
        "precision":           round(prec, 2),
        "recall":              round(rec,  2),
        "feature_importances": feat_imp,
        "training_samples":    len(df),
        "features_used":       available,
        "features_missing":    missing,
    }

if __name__ == "__main__":
    train_model()

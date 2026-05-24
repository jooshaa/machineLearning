import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_validate
import sys

# Add parent directory to path so we can import strategy_volume_delta
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import strategy_volume_delta

def train_model():
    print("Collecting signals from backtest...")
    all_signals = []
    for chunk in strategy_volume_delta.stream_main():
        all_signals.extend(chunk)
        
    if not all_signals:
        return {"error": "No signals generated."}
        
    df = pd.DataFrame(all_signals)
    
    # Filter out timeouts
    df = df[df['outcome'] != 'timeout'].copy()
    
    if len(df) < 10:
        return {"error": "Not enough data to train."}
        
    # Feature engineering
    # entry_time has 'Z' at the end, pd.to_datetime handles it
    df['entry_time_dt'] = pd.to_datetime(df['entry_time'].str.replace('Z', ''), errors='coerce')
    df['hour'] = df['entry_time_dt'].dt.hour
    df['day_of_week'] = df['entry_time_dt'].dt.dayofweek
    df['impulse_points'] = abs(df['tp_price'] - df['entry_price'])
    
    # Handle boolean absorption if present
    df['absorption'] = df['absorption'].astype(int)
    
    # Target
    df['target'] = (df['outcome'] == 'win').astype(int)
    
    features = ['hour', 'day_of_week', 'sl_distance', 'reward_risk', 'score', 'absorption', 'impulse_points']
    X = df[features]
    y = df['target']
    
    # Train
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    
    # Cross validation (5-fold)
    cv_results = cross_validate(model, X, y, cv=5, scoring=['accuracy', 'precision', 'recall'])
    
    acc = cv_results['test_accuracy'].mean()
    prec = cv_results['test_precision'].mean()
    rec = cv_results['test_recall'].mean()
    
    # Fit on all data for feature importances and saving
    model.fit(X, y)
    
    importances = model.feature_importances_
    feat_imp = {feat: round(float(imp), 4) for feat, imp in zip(features, importances)}
    
    # Sort feature importances
    feat_imp = dict(sorted(feat_imp.items(), key=lambda item: item[1], reverse=True))
    
    # Save model
    models_dir = os.path.join(parent_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, 'volume_delta_rf.pkl')
    joblib.dump(model, model_path)
    
    print(f"Accuracy: {acc:.2f}")
    print(f"Precision: {prec:.2f}")
    print(f"Recall: {rec:.2f}")
    print(f"Feature Importances: {feat_imp}")
    
    return {
        "accuracy": round(float(acc), 2),
        "precision": round(float(prec), 2),
        "recall": round(float(rec), 2),
        "feature_importances": feat_imp,
        "training_samples": len(df)
    }

if __name__ == "__main__":
    train_model()

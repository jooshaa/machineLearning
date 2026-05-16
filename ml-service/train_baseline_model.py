import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import pickle
import os
import matplotlib.pyplot as plt
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    confusion_matrix, classification_report, roc_auc_score, roc_curve
)
import seaborn as sns

def train_manual_edge_model():
    print("🚀 Loading DISCRETIONARY manual trade dataset...")
    data_path = 'orderflow_ml/manual_trade_dataset.csv'
    
    if not os.path.exists(data_path):
        print(f"❌ Error: {data_path} not found. Run extract_manual_trade_features.py first.")
        return

    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return
        
    print(f"✅ Loaded {len(df)} manual trades.")

    # 1. Target Normalization
    # Convert 'Win'/'Loss' to 1/0
    if 'result' in df.columns:
        df['target_is_good_setup'] = df['result'].apply(lambda x: 1 if str(x).lower() == 'win' else 0)
        print(f"🎯 Target created from 'result' column.")
    else:
        print("❌ Error: 'result' column missing for target generation.")
        return

    target_col = 'target_is_good_setup'

    # 2. Preprocessing & Sorting
    if 'timestamp_utc' in df.columns:
        print("🕒 Parsing timestamps...")
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'], format='mixed', errors='coerce', utc=True)
        df = df.dropna(subset=['timestamp_utc', target_col])
        df = df.sort_values('timestamp_utc').reset_index(drop=True)
        print(f"📅 Data sorted. Remaining rows: {len(df)}")

    # 3. Discretionary Metadata & Reason Encoding
    # Handle 'reasons' (pipe-separated)
    if 'reasons' in df.columns:
        print("🏷️ Encoding trade reasons...")
        # Simple multi-label binarization
        reasons_series = df['reasons'].fillna('').str.get_dummies(sep='|')
        # Prefix for clarity
        reasons_series.columns = ['reason_' + col for col in reasons_series.columns]
        df = pd.concat([df, reasons_series], axis=1)

    # 4. Feature Selection
    # Drop non-feature columns
    drop_cols = [
        'trade_id', 'timestamp_utc', 'entry_price', 'outcome_r', 'result', 
        'description', 'reasons', 'symbol', 'location', 'regime', 'side', 'session'
    ]
    
    # Encode standard categorical features
    categorical_cols = ['direction', 'event_type', 'spoof_context', 'trend']
    for col in categorical_cols:
        if col in df.columns:
            print(f"🏷️ Encoding categorical feature: {col}")
            df = pd.get_dummies(df, columns=[col], drop_first=True)

    X = df.drop(columns=[target_col] + [c for c in drop_cols if c in df.columns], errors='ignore')
    X = X.select_dtypes(include=[np.number])
    y = df[target_col]

    # Handle NaNs (common in L3 due to sparse snapshots)
    if X.isnull().values.any():
        print("⚠️ Filling NaNs with median values...")
        X = X.fillna(X.median())

    feature_names = X.columns.tolist()
    
    # 5. Diagnostics
    print("\n" + "="*40)
    print("📊 DATASET DIAGNOSTICS")
    print("="*40)
    print(f"Total Samples    : {len(df)}")
    print(f"Feature Count    : {len(feature_names)}")
    print(f"Class Balance (1): {y.mean():.2%}")
    print("="*40)

    if len(df) < 10:
        print("⚠️ Warning: Extremely small sample size. Results will be volatile.")

    # 6. Time-Series Split
    # With very small data, we use a smaller holdout or just CV
    test_size = max(1, int(len(df) * 0.2))
    split_idx = len(df) - test_size
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # 7. Model Training (XGBoost)
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )

    print("🧠 Training Manual Edge XGBoost model...")
    
    # Only do CV if we have enough samples
    if len(X_train) > 10:
        tscv = TimeSeriesSplit(n_splits=min(5, len(X_train)//2))
        cv_scores = cross_val_score(model, X_train, y_train, cv=tscv, scoring='roc_auc')
        print(f"📉 Cross-Validation ROC-AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    model.fit(X_train, y_train)

    # 8. Evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None
    
    print("\n" + "="*40)
    print("📈 PERFORMANCE METRICS (HOLDOUT SET)")
    print("="*40)
    print(f"Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
    if len(np.unique(y_test)) > 1 and y_proba is not None:
        roc_auc = roc_auc_score(y_test, y_proba)
        print(f"ROC-AUC   : {roc_auc:.4f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("="*40)

    # 9. Save Model
    os.makedirs('models', exist_ok=True)
    model_path = 'models/manual_edge_xgb.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump({'model': model, 'feature_names': feature_names}, f)
    print(f"💾 Model saved to {model_path}")

    # 10. Visualizations
    plots_dir = 'orderflow_ml/manual_plots'
    os.makedirs(plots_dir, exist_ok=True)
    
    # Feature Importance
    plt.figure(figsize=(10, 8))
    feat_importances = pd.Series(model.feature_importances_, index=feature_names)
    feat_importances.nlargest(15).plot(kind='barh', color='darkorange')
    plt.title("Top 15 Predictive Features (Manual Edge)")
    plt.tight_layout()
    plt.savefig(f'{plots_dir}/feature_importance.png')
    
    # SHAP
    try:
        print("🔍 Running SHAP analysis...")
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_test, show=False)
        plt.title("SHAP Summary: Microstructure Impact on Discretionary Edge")
        plt.tight_layout()
        plt.savefig(f'{plots_dir}/shap_summary.png')
        print(f"📊 Plots saved to {plots_dir}/")
    except Exception as e:
        print(f"⚠️ SHAP failed: {e}")

if __name__ == "__main__":
    train_manual_edge_model()

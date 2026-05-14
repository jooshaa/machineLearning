import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score, classification_report
import shap
import matplotlib.pyplot as plt
import os

def train_baseline_model(csv_path):
    print(f"Loading dataset from {csv_path}...")
    if not os.path.exists(csv_path):
        print(f"File {csv_path} not found. Please run build_ml_dataset.py first.")
        return
        
    df = pd.DataFrame(pd.read_csv(csv_path))
    
    # Исключаем метаданные из фичей
    exclude_cols = ['trade_id', 'timestamp_utc', 'direction', 'entry_price', 'outcome_r', 'target_is_good_setup', 'result']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    
    X = df[feature_cols].copy()
    y = df['target_is_good_setup']
    
    # Конвертируем строки (categorical) в тип category для XGBoost
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = X[col].astype('category')
    
    # Базовое разбиение: 80% train, 20% test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
    
    print(f"Training dataset: {X_train.shape[0]} rows. Test dataset: {X_test.shape[0]} rows.")
    print("Training XGBoost baseline model on REAL L3 features...")
    
    # Настройки для baseline XGBoost
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss',
        enable_categorical=True
    )
    
    model.fit(X_train, y_train)
    
    # Предикты
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    # Метрики
    print("\n=== Model Evaluation ===")
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.3f}")
    print(f"ROC AUC:   {roc_auc_score(y_test, y_pred_proba):.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # SHAP анализ
    print("\n=== Running SHAP Analysis ===")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)
    
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'mean_abs_shap': np.abs(shap_values).mean(axis=0)
    }).sort_values('mean_abs_shap', ascending=False)
    
    print("\nTop Features by SHAP value:")
    print(shap_df.head(10).to_string(index=False))
    
    shap.summary_plot(shap_values, X_test, show=False)
    plt.tight_layout()
    plt.savefig('shap_summary.png')
    print("\nSaved SHAP summary plot to shap_summary.png")
    
    # Ранжирование setup quality (confidence score)
    print("\n=== Sample Setup Confidence Scores (Test Set) ===")
    test_results = X_test.copy()
    test_results['actual_target'] = y_test
    test_results['confidence_score'] = y_pred_proba
    
    top_features = shap_df['feature'].head(2).tolist()
    
    top_setups = test_results.sort_values('confidence_score', ascending=False).head(5)
    cols_to_show = ['confidence_score', 'actual_target'] + top_features
    print(top_setups[cols_to_show])

if __name__ == "__main__":
    CSV_PATH = "/Users/asal/Desktop/own/machine learning/ml-service/orderflow_ml/ml_dataset.csv"
    train_baseline_model(CSV_PATH)

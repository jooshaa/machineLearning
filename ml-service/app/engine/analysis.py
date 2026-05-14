import pandas as pd
import numpy as np
import os
from app.engine.auto_edge import edge_validator

def analyze_trade_history() -> dict:
    """
    Edge Stability Analysis Dashboard Engine.
    - Regime Map
    - Stability Ranking
    - Decay Sensitivity
    """
    path = "data/processed/trades.parquet"
    if not os.path.exists(path):
        return {"error": "No trade history found. Run backtests first."}
    
    df = pd.read_parquet(path).sort_values('ts')
    if len(df) < 15:
        return {"error": "Insufficient sample size for stability analysis."}

    # 1. Regime Performance Breakdown
    regime_stats = {}
    if 'regime' in df.columns:
        regime_stats = df.groupby('regime').agg(
            avg_R=('outcome_R', 'mean'),
            win_rate=('is_win', lambda x: x.mean() * 100),
            count=('outcome_R', 'count')
        ).to_dict(orient='index')

    # 2. Stability Ranking (from Validator)
    validated_segments = edge_validator.validate_all_edges()

    # 3. Enhanced Decay Check
    df['lt_exp'] = df['outcome_R'].rolling(window=min(200, len(df))).mean()
    df['st_exp'] = df['outcome_R'].rolling(window=min(50, len(df))).mean()
    
    recent_expectancy = df['st_exp'].iloc[-1]
    long_term_expectancy = df['lt_exp'].iloc[-1]
    
    is_decaying = recent_expectancy < (long_term_expectancy * 0.7)
    decay_alert = "WARNING: Edge showing significant weakness vs baseline." if is_decaying else "Stable"

    # 4. Score Correlation
    correlation = df['score'].corr(df['outcome_R'])

    return {
        "summary": {
            "total_trades": len(df),
            "win_rate": round(float(df['is_win'].mean() * 100), 1),
            "avg_R": round(float(df['outcome_R'].mean()), 2),
            "score_correlation": round(float(correlation), 3),
            "decay_status": "decaying" if is_decaying else "stable",
            "decay_alert": decay_alert
        },
        "regime_performance": regime_stats,
        "validated_edge": validated_segments,
        "rolling_expectancy": {
            "short_term": df['st_exp'].dropna().tail(30).tolist(),
            "long_term": df['lt_exp'].dropna().tail(30).tolist()
        }
    }

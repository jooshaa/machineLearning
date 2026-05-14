import pandas as pd
import numpy as np

def detect_market_regime(df: pd.DataFrame) -> dict:
    """
    Detects current market regime based on volatility and price action.
    """
    if df.empty or len(df) < 50:
        return {"regime_type": "unknown", "volatility": 0, "trend_strength": 0}

    # 1. Volatility (Standard Deviation of price changes)
    returns = df['price'].pct_change().dropna()
    vol = returns.std() * np.sqrt(252 * 6.5 * 60) # Annualized vol estimate
    
    vol_regime = "high_vol" if vol > 0.15 else "low_vol"

    # 2. Trend Strength (using slope of moving average)
    ma = df['price'].rolling(window=50).mean()
    slope = (ma.iloc[-1] - ma.iloc[-10]) / ma.iloc[-10] if not ma.isna().iloc[-1] else 0
    
    trend_regime = "range"
    if slope > 0.0001: trend_regime = "trend_up"
    elif slope < -0.0001: trend_regime = "trend_down"

    # 3. Regime Classification
    regime_type = f"{trend_regime}_{vol_regime}"
    
    return {
        "regime_type": regime_type,
        "volatility": round(float(vol), 4),
        "trend_strength": round(float(slope), 6),
        "is_trending": trend_regime != "range",
        "is_high_vol": vol_regime == "high_vol"
    }

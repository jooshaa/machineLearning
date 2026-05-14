import pandas as pd
import numpy as np

def compute_context(df: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """
    Computes context for each event:
    - location: VAH, VAL, POC, LVN, MID (using rolling volume profile)
    - trend: up, down, range
    - session: Asia, London, NY
    - volatility: rolling std of price
    - distance_to_level: nearest VP level distance
    - recent_range: high-low over last N periods
    """
    if df.empty:
        return df
        
    ctx = df.copy()
    
    # 1. Session Detection
    if 'ts' in ctx.columns:
        hours = pd.to_datetime(ctx['ts']).dt.hour
    elif pd.api.types.is_datetime64_any_dtype(ctx.index):
        hours = ctx.index.hour
    else:
        hours = pd.Series([0] * len(ctx), index=ctx.index)
        
    def get_session(h):
        if 8 <= h < 13: return 'London'
        elif 13 <= h < 20: return 'NY'
        else: return 'Asia'
        
    ctx['session'] = hours.apply(get_session)
    
    # 2. Rolling Volatility & Range
    ctx['volatility'] = ctx['price'].rolling(window=100, min_periods=10).std().fillna(0)
    rolling_high = ctx['price'].rolling(window=100, min_periods=10).max()
    rolling_low = ctx['price'].rolling(window=100, min_periods=10).min()
    ctx['recent_range'] = (rolling_high - rolling_low).fillna(0)
    
    # 3. Trend Detection (Simple MA cross for MBO event scale)
    fast_ma = ctx['price'].rolling(50, min_periods=10).mean()
    slow_ma = ctx['price'].rolling(200, min_periods=20).mean()
    
    ctx['trend'] = 'range'
    ctx.loc[(fast_ma > slow_ma) & (ctx['price'] > fast_ma), 'trend'] = 'up'
    ctx.loc[(fast_ma < slow_ma) & (ctx['price'] < fast_ma), 'trend'] = 'down'
    
    # 4. Location vs Volume Profile (Approximation using rolling price quantiles for VAH/VAL/POC)
    # In a full engine, we'd build a tick-level volume profile. We approximate here.
    vah = ctx['price'].rolling(500, min_periods=50).quantile(0.70)
    val = ctx['price'].rolling(500, min_periods=50).quantile(0.30)
    poc = ctx['price'].rolling(500, min_periods=50).median() # Approximate POC
    
    def get_location(p, v_h, v_l, p_c):
        if pd.isna(v_h): return 'MID'
        if p >= v_h: return 'VAH'
        if p <= v_l: return 'VAL'
        if abs(p - p_c) < (v_h - v_l) * 0.1: return 'POC'
        return 'MID'
        
    ctx['location'] = [get_location(p, vh, vl, pc) for p, vh, vl, pc in zip(ctx['price'], vah, val, poc)]
    
    # Distance to nearest level (VAH, VAL, POC)
    ctx['distance_to_level'] = np.minimum(
        np.minimum(abs(ctx['price'] - vah), abs(ctx['price'] - val)),
        abs(ctx['price'] - poc)
    ).fillna(0)
    
    return ctx

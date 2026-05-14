import pandas as pd

def apply_decision_rules(df: pd.DataFrame, score_threshold: float = 0.5) -> pd.DataFrame:
    """
    Decision Engine: Filters out weak or conflicting events.
    Returns only events that are cleared for execution.
    """
    if df.empty:
        return df
        
    dec = df.copy()
    
    # Base requirements
    # 1. Score > threshold
    pass_score = dec['event_score'] > score_threshold
    
    # 2. Context aligns
    # Avoid trading in a 'range' if volatility is extremely low
    # We allow range trading if volatility is decent, or if at extremes (VAH/VAL)
    avg_vol = dec['volatility'].mean() if 'volatility' in dec.columns else 1.0
    pass_volatility = ~((dec.get('trend') == 'range') & (dec.get('volatility', 0) < avg_vol * 0.5) & (dec.get('location') == 'MID'))
    
    # 3. Conflict filter
    # e.g., Absorption indicates BUY (delta < 0 absorbing selling), but trend is strongly 'down' and location is 'MID'
    # We want to catch falling knives only at VAL.
    conflict = (
        (dec.get('absorption_flag') == True) & 
        (dec.get('delta', 0) < 0) & 
        (dec.get('trend') == 'down') & 
        (~dec.get('location').isin(['VAL', 'LVN']))
    )
    pass_conflict = ~conflict
    
    # Execute only if all pass
    dec['is_tradable'] = pass_score & pass_volatility & pass_conflict
    
    return dec

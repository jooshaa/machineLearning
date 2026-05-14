import pandas as pd
import numpy as np

def score_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scores each event based on aggregated context, sequence, and raw MBO strengths.
    Score normalized to [0,1].
    """
    if df.empty:
        return df
        
    scored = df.copy()
    
    # Weights for the scoring formula
    W_DELTA = 0.2
    W_LIQUIDITY = 0.2
    W_ABSORPTION = 0.2
    W_SPOOF = 0.1
    W_LOCATION = 0.15
    W_SEQUENCE = 0.15
    
    # Normalize inputs to approx [0,1] range
    
    # 1. Delta strength (relative to rolling volume)
    # We use abs(delta) / rolling_vol. Assuming rolling_vol was 50-tick sum, max is ~1.0
    # Let's approximate based on raw delta
    delta_norm = (scored['delta'].abs() / (scored['size'].abs() + 1e-9)).clip(0, 1)
    
    # 2. Liquidity imbalance strength
    # > 1 means heavy bid, < 1 means heavy ask. We want extreme values.
    imb = scored['orderbook_imbalance'].fillna(1.0)
    # distance from 1.0, scaled to [0,1]
    imb_strength = (abs(imb - 1.0) / 3.0).clip(0, 1)
    
    # 3. Absorption / Trap strength
    # Normalize strength
    abs_str = (scored.get('absorption_strength', 0) / 10.0).clip(0, 1)
    trap_str = (scored.get('trap_strength', 0) / 20.0).clip(0, 1)
    pattern_strength = np.maximum(abs_str, trap_str)
    
    # 4. Spoof activity
    spoof_norm = (scored.get('spoof_activity', 0) / 5.0).clip(0, 1)
    
    # 5. Location Weight
    # High edge if occurring at VAH or VAL. Lower edge at MID.
    def loc_weight(loc):
        if loc in ['VAH', 'VAL']: return 1.0
        if loc == 'POC': return 0.8
        if loc == 'LVN': return 0.9
        return 0.3
    
    loc_w = scored['location'].apply(loc_weight) if 'location' in scored.columns else 0.5
    
    # 6. Sequence Weight
    seq_w = scored.get('sequence_strength', 0.5)
    
    # Calculate weighted sum
    raw_score = (
        delta_norm * W_DELTA +
        imb_strength * W_LIQUIDITY +
        pattern_strength * W_ABSORPTION +
        spoof_norm * W_SPOOF +
        loc_w * W_LOCATION +
        seq_w * W_SEQUENCE
    )
    
    # Final normalization
    scored['event_score'] = raw_score.clip(0, 1)
    
    return scored

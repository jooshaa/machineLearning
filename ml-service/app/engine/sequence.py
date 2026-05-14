import pandas as pd

def compute_sequence(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    Tracks the sequence of the last N events.
    Encodes sequence as features.
    df must have 'event_type' column.
    """
    if df.empty or 'event_type' not in df.columns:
        return df
        
    seq = df.copy()
    
    # We only care about actual events, not 'normal' background ticks
    # However, for sequence encoding, we look back at the last N *actual* events.
    
    # Create a mask of real events
    is_event = seq['event_type'] != 'normal'
    
    # Extract just the events
    events_only = seq[is_event][['event_type']].copy()
    
    # Shift to get previous events
    for i in range(1, window + 1):
        events_only[f'prev_event_{i}'] = events_only['event_type'].shift(i).fillna('none')
        
    # Build sequence string: e.g., "spoof->absorption->trap"
    def build_seq_string(row):
        parts = []
        for i in range(window, 0, -1):
            val = row.get(f'prev_event_{i}', 'none')
            if val != 'none':
                parts.append(val)
        parts.append(row['event_type'])
        return "->".join(parts)
        
    events_only['sequence_pattern'] = events_only.apply(build_seq_string, axis=1)
    
    # Join back to main dataframe
    # Normal ticks get 'none' sequence
    seq = seq.join(events_only[['sequence_pattern']], how='left')
    seq['sequence_pattern'] = seq['sequence_pattern'].fillna('none')
    
    # Transition strength: custom metric based on order flow logic
    # e.g., spoof -> absorption -> trap is very strong manipulation
    def get_seq_strength(pattern: str) -> float:
        if "spoof->absorption" in pattern: return 0.9
        if "absorption->trap" in pattern: return 0.8
        if "spoof->trap" in pattern: return 0.85
        if "trap" in pattern: return 0.7
        if "absorption" in pattern: return 0.6
        if "spoof" in pattern: return 0.5
        return 0.1
        
    seq['sequence_strength'] = seq['sequence_pattern'].apply(get_seq_strength)
    
    return seq

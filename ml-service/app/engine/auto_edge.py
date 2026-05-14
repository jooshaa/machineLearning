import pandas as pd
import numpy as np
import os
from scipy import stats

VALIDATED_TRADES_PATH = "data/processed/trades.parquet"

class EdgeValidator:
    def __init__(self, min_trades=15, t_stat_threshold=2.5): # Increased threshold for multiple testing correction
        self.min_trades = min_trades
        self.t_stat_threshold = t_stat_threshold
        self.validated_segments = {} 

    def validate_all_edges(self):
        """
        Full Edge Stability Engine Validation:
        - Regime-Aware Analysis
        - Multiple Testing Correction (Higher T-Stat)
        - Decay Sensitivity
        """
        if not os.path.exists(VALIDATED_TRADES_PATH):
            return {}

        df = pd.read_parquet(VALIDATED_TRADES_PATH)
        if len(df) < self.min_trades * 2:
            return {}

        df = df.sort_values('ts')
        
        # 1. Advanced Decay Check
        # Compare short term (50) vs long term (200)
        df['lt_exp'] = df['outcome_R'].rolling(window=min(200, len(df))).mean()
        df['st_exp'] = df['outcome_R'].rolling(window=min(50, len(df))).mean()
        
        # 2. Train/Test Split
        split_idx = int(len(df) * 0.7)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        # 3. Regime-Aware Segment Analysis
        # Note: 'regime' should be logged in trades.parquet. 
        # If not present in older logs, we default to 'all'
        group_cols = ['event_type', 'location', 'session']
        if 'regime' in df.columns:
            group_cols.append('regime')

        train_segments = self._analyze_segments(train_df, group_cols)
        test_segments = self._analyze_segments(test_df, group_cols)

        validated = {}
        for key, train_metrics in train_segments.items():
            if key not in test_segments: continue
            
            test_metrics = test_segments[key]
            
            # Robustness Criteria:
            # - Expectancy > 0 in both
            # - T-Stat > 2.5 (Bonferroni-lite adjustment)
            # - Recent performance (st_exp) not significantly below long term
            
            if (train_metrics['expectancy'] > 0 and 
                test_metrics['expectancy'] > 0 and 
                train_metrics['t_stat'] >= self.t_stat_threshold and
                train_metrics['count'] >= self.min_trades):
                
                stability = self._compute_stability(train_metrics, test_metrics, df)
                
                validated[key] = {
                    "stability_score": stability,
                    "expectancy": test_metrics['expectancy'],
                    "t_stat": train_metrics['t_stat'],
                    "count": train_metrics['count'] + test_metrics['count'],
                    "is_stable": stability > 0.5
                }

        self.validated_segments = validated
        return validated

    def _analyze_segments(self, df, group_cols):
        segments = {}
        grouped = df.groupby(group_cols)
        
        for name, group in grouped:
            # Handle both single and multi-column grouping
            key = "|".join(str(x) for x in (name if isinstance(name, tuple) else [name]))
            n = len(group)
            if n < 5: continue
            
            mean_r = group['outcome_R'].mean()
            std_r = group['outcome_R'].std()
            t_stat = mean_r / (std_r / np.sqrt(n)) if std_r > 0 else 0
            
            segments[key] = {"expectancy": mean_r, "t_stat": t_stat, "count": n}
        return segments

    def _compute_stability(self, train, test, df):
        # Ratio check
        ratio = min(1.0, test['expectancy'] / train['expectancy']) if train['expectancy'] > 0 else 0
        # Decay check
        recent = df['st_exp'].iloc[-1]
        long_term = df['lt_exp'].iloc[-1]
        decay_penalty = 1.0
        if recent < long_term * 0.8: decay_penalty = 0.5 # Apply penalty if weakening
        
        return round(ratio * decay_penalty, 2)

    def is_trade_allowed(self, event, current_regime: str = "unknown") -> tuple[bool, float]:
        if not self.validated_segments:
            self.validate_all_edges()
            
        # ── WARM-UP MODE ──
        # If we have no validated segments (not enough history), 
        # allow trades to collect data for future validation.
        if not self.validated_segments:
            return True, 0.5 # Default stability for data collection
            
        # Try regime-specific key first
        key_regime = f"{event.get('event_type')}|{event.get('location')}|{event.get('session')}|{current_regime}"
        key_all = f"{event.get('event_type')}|{event.get('location')}|{event.get('session')}"
        
        seg = self.validated_segments.get(key_regime) or self.validated_segments.get(key_all)
        
        if seg and seg['stability_score'] >= 0.4:
            return True, seg['stability_score']
        return False, 0.0

edge_validator = EdgeValidator()

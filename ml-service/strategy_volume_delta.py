import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import existing infrastructure
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

# Parameters
IMPULSE_MIN_POINTS = 100      # minimum NQ points for valid impulse
IMPULSE_MAX_DURATION_MIN = 120
MIN_DELTA_CONTRACTS = 250     # minimum contracts for large delta zone
TP_POINTS = 150               # take profit in NQ points  
SL_POINTS = 60                # stop loss in NQ points
CONFIRMATION_WINDOW_MIN = 30  # wait for confirmation within 30 min of zone touch

def find_impulses(df):
    """
    Detects impulse moves from features data.
    df must have 'price' and 'ts' (or index as datetime).
    """
    # Resample to 1-min candles for easier impulse detection
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'ts' in df.columns:
            df = df.set_index('ts')
        else:
            df.index = pd.to_datetime(df.index)
            
    ohlc = df['price'].resample('1min').ohlc()
    ohlc.dropna(inplace=True)
    
    impulses = []
    window_size = IMPULSE_MAX_DURATION_MIN
    
    for i in range(len(ohlc)):
        window = ohlc.iloc[i : i + window_size]
        if len(window) < 2:
            continue
            
        min_price = window['low'].min()
        max_price = window['high'].max()
        
        if max_price - min_price >= IMPULSE_MIN_POINTS:
            min_idx = window['low'].argmin()
            max_idx = window['high'].argmax()
            
            if min_idx < max_idx: # Upward impulse
                start_time = window.index[min_idx]
                stop_time = window.index[max_idx]
                impulses.append({
                    'type': 'up',
                    'start': start_time,
                    'stop': stop_time,
                    'price_start': min_price,
                    'price_stop': max_price,
                    'points': max_price - min_price
                })
            elif max_idx < min_idx: # Downward impulse
                start_time = window.index[max_idx]
                stop_time = window.index[min_idx]
                impulses.append({
                    'type': 'down',
                    'start': start_time,
                    'stop': stop_time,
                    'price_start': max_price,
                    'price_stop': min_price,
                    'points': max_price - min_price
                })
                
    # Filter overlapping impulses (keep the first non-overlapping)
    filtered = []
    last_stop = None
    for imp in impulses:
        if last_stop is None or imp['start'] > last_stop:
            filtered.append(imp)
            last_stop = imp['stop']
            
    print(f"Found {len(filtered)} valid impulses.")
    return filtered

def build_volume_profile(df, start_time, stop_time):
    """Builds volume and delta profile on impulse range."""
    mask = (df.index >= start_time) & (df.index <= stop_time)
    range_data = df[mask].copy()
    
    if range_data.empty:
        return pd.DataFrame()
        
    if 'delta' not in range_data.columns:
        range_data['delta'] = np.where(range_data['side'] == 'A', range_data['size'], -range_data['size'])
        
    profile = range_data.groupby('price').agg({
        'size': 'sum',
        'delta': 'sum'
    }).rename(columns={'size': 'volume'})
    
    return profile

def find_delta_zones(profile):
    """Identifies large delta zones (>250 contracts)."""
    if profile.empty:
        return {'buy': [], 'sell': []}
        
    buy_zones = profile[profile['delta'] > MIN_DELTA_CONTRACTS].index.tolist()
    sell_zones = profile[profile['delta'] < -MIN_DELTA_CONTRACTS].index.tolist()
    
    return {'buy': buy_zones, 'sell': sell_zones}

def backtest(features_df, impulses):
    """Backtests the strategy on detected impulses."""
    signals = []
    
    if not isinstance(features_df.index, pd.DatetimeIndex):
        features_df = features_df.set_index('ts')
        
    candles = features_df['price'].resample('1min').ohlc()
    
    for imp in impulses:
        start_time = imp['start']
        stop_time = imp['stop']
        imp_type = imp['type']
        
        profile = build_volume_profile(features_df, start_time, stop_time)
        zones = find_delta_zones(profile)
        
        target_zones = zones['buy'] if imp_type == 'up' else zones['sell']
        if not target_zones:
            continue
            
        post_impulse = features_df[features_df.index > stop_time]
        if post_impulse.empty:
            continue
            
        touched = False
        touch_time = None
        target_price = None
        
        for ts, row in post_impulse.iterrows():
            price = row['price']
            for zp in target_zones:
                if abs(price - zp) <= 1.0: # 1 point tolerance
                    touched = True
                    touch_time = ts
                    target_price = zp
                    break
            if touched:
                break
                
        if touched:
            conf_window = post_impulse[(post_impulse.index > touch_time) & 
                                       (post_impulse.index <= touch_time + timedelta(minutes=CONFIRMATION_WINDOW_MIN))]
            
            if conf_window.empty:
                continue
                
            window_candles = candles[(candles.index > touch_time) & (candles.index <= touch_time + timedelta(minutes=CONFIRMATION_WINDOW_MIN))]
            
            for c_ts, c_row in window_candles.iterrows():
                c_trades = features_df[(features_df.index >= c_ts) & (features_df.index < c_ts + timedelta(minutes=1))]
                if c_trades.empty:
                    continue
                poc = c_trades.groupby('price')['size'].sum().idxmax()
                
                close_price = c_row['close']
                
                cvd_at_touch = conf_window.loc[conf_window.index <= c_ts, 'cvd'].iloc[-1] if not conf_window.loc[conf_window.index <= c_ts].empty else 0
                current_cvd = c_trades['cvd'].iloc[-1] if 'cvd' in c_trades.columns else 0
                
                cvd_confirmed = False
                if imp_type == 'up' and current_cvd > cvd_at_touch:
                    cvd_confirmed = True
                elif imp_type == 'down' and current_cvd < cvd_at_touch:
                    cvd_confirmed = True
                    
                if imp_type == 'up' and close_price > poc and cvd_confirmed:
                    signals.append({
                        'ts': c_ts,
                        'type': 'delta_zone_return',
                        'direction': 'buy',
                        'entry': close_price,
                        'stop': target_price - SL_POINTS,
                        'target': close_price + TP_POINTS,
                        'impulse_start': start_time,
                        'impulse_stop': stop_time
                    })
                    break
                elif imp_type == 'down' and close_price < poc and cvd_confirmed:
                    signals.append({
                        'ts': c_ts,
                        'type': 'delta_zone_return',
                        'direction': 'sell',
                        'entry': close_price,
                        'stop': target_price + SL_POINTS,
                        'target': close_price - TP_POINTS,
                        'impulse_start': start_time,
                        'impulse_stop': stop_time
                    })
                    break
                    
    return pd.DataFrame(signals)

def main():
    print("🚀 Starting Volume Delta Profile Strategy Backtest...")
    
    cache_dir = "data/raw/mbo/NQ"
    if not os.path.exists(cache_dir):
        print(f"Cache directory {cache_dir} missing. Creating mock data for demonstration.")
        create_mock_data()
        
    files = [f for f in os.listdir(cache_dir) if f.endswith(".parquet")]
    if not files:
        print("No parquet files found. Creating mock data.")
        create_mock_data()
        files = ["2023-01-03.parquet"]
        
    all_signals = []
    
    for filename in files:
        path = os.path.join(cache_dir, filename)
        print(f"\nProcessing {filename}...")
        
        try:
            mbo_df = pd.read_parquet(path)
            if mbo_df.empty:
                continue
                
            if mbo_df['price'].max() > 1000000:
                mbo_df['price'] = mbo_df['price'] / 1e9
                
            print("Building order book and extracting trade events...")
            events = process_mbo_stream(mbo_df)
            if not events:
                print("No events generated.")
                continue
            events_df = pd.DataFrame(events)
            
            print("Extracting features...")
            features = extract_l3_features(mbo_df, events_df)
            
            print("Running strategy...")
            impulses = find_impulses(features)
            signals = backtest(features, impulses)
            
            if not signals.empty:
                all_signals.append(signals)
                print(f"Generated {len(signals)} signals for {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
    if all_signals:
        result_df = pd.concat(all_signals, ignore_index=True)
        os.makedirs("orderflow_ml", exist_ok=True)
        result_df.to_csv("orderflow_ml/volume_delta_dataset.csv", index=False)
        print(f"\n✅ Results exported to orderflow_ml/volume_delta_dataset.csv. Total signals: {len(result_df)}")
    else:
        print("\n❌ No signals generated across all files.")

def create_mock_data():
    """Creates a mock dataset that resembles Databento MBO data."""
    print("Generating mock data for testing...")
    os.makedirs("data/raw/mbo/NQ", exist_ok=True)
    path = "data/raw/mbo/NQ/2023-01-03.parquet"
    
    dates = pd.date_range(start="2023-01-03 14:30:00", periods=10000, freq="100ms")
    
    prices = [15000.0]
    for i in range(1, len(dates)):
        if 2000 < i < 4000:
            prices.append(prices[-1] + np.random.uniform(0, 0.25)) # Upward impulse
        elif 6000 < i < 8000:
            prices.append(prices[-1] - np.random.uniform(0, 0.25)) # Downward return
        else:
            prices.append(prices[-1] + np.random.uniform(-0.25, 0.25))
            
    df = pd.DataFrame({
        'price': prices,
        'size': np.random.randint(1, 100, size=len(dates)),
        'action': 'T',
        'side': np.random.choice(['A', 'B'], size=len(dates)),
        'order_id': np.random.randint(1000, 9999, size=len(dates)),
        'symbol': 'NQ.FUT'
    }, index=dates)
    
    # Add some large delta in the impulse range
    df.loc[df.index[3000:3500], 'size'] = 500
    df.loc[df.index[3000:3500], 'side'] = 'A'
    
    df.to_parquet(path)
    print(f"Mock data saved to {path}")

if __name__ == "__main__":
    main()

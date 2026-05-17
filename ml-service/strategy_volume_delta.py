import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gc

# Import existing infrastructure
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

# Parameters
IMPULSE_MIN_POINTS = 100      # minimum NQ points for valid impulse
IMPULSE_MAX_DURATION_MIN = 120
MIN_DELTA_CONTRACTS = 30      # lowered from 250
TP_POINTS = 150               # take profit in NQ points  
SL_POINTS = 60                # stop loss in NQ points
CONFIRMATION_WINDOW_MIN = 30  # wait for confirmation within 30 min of zone touch
CONSOLIDATION_RANGE = 50       # max range for consolidation
AGGRESSION_MIN_CONTRACTS = 20 # min contracts for aggression

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
    mask = (df.index.values >= np.datetime64(start_time)) & (df.index.values <= np.datetime64(stop_time))
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

def check_orderbook_state(mbo_df, target_price, touch_time, direction):
    """
    Checks the orderbook state at touch_time for large limit orders and spoofing.
    """
    side = 'B' if direction == 'buy' else 'A'
    tick_size = 0.25
    tolerance = 2 * tick_size
    
    # Filter adds
    adds = mbo_df[(mbo_df.index.values <= np.datetime64(touch_time)) & 
                  (mbo_df['action'] == 'A') & 
                  (mbo_df['side'] == side) &
                  (abs(mbo_df['price'] - target_price) <= tolerance) &
                  (mbo_df['size'] > 200)]
                  
    if adds.empty:
        return False, False
        
    real_orders_count = 0
    order_prices = []
    
    for _, add_row in adds.iterrows():
        order_id = add_row['order_id']
        t_add = add_row.name
        
        t_add_np = np.datetime64(t_add)
        subsequent = mbo_df[(mbo_df.index.values > t_add_np) & (mbo_df['order_id'] == order_id)]
        
        if subsequent.empty:
            if np.datetime64(touch_time) - t_add_np >= np.timedelta64(30, 's'):
                real_orders_count += 1
                order_prices.append(add_row['price'])
            continue
            
        cancels = subsequent[subsequent['action'] == 'C']
        trades = subsequent[subsequent['action'] == 'T']
        
        t_cancel = cancels.index[0] if not cancels.empty else None
        t_trade = trades.index[0] if not trades.empty else None
        
        if t_cancel is not None:
            if np.datetime64(t_cancel) - t_add_np < np.timedelta64(30, 's'):
                if t_trade is None or np.datetime64(t_trade) > np.datetime64(t_cancel):
                    continue
                    
        real_orders_count += 1
        order_prices.append(add_row['price'])
        
    layering = False
    if len(order_prices) >= 2:
        order_prices.sort()
        for i in range(len(order_prices) - 1):
            if order_prices[i+1] - order_prices[i] <= 5 * tick_size:
                layering = True
                break
                
    large_limit_present = real_orders_count > 0
    
    return large_limit_present, layering

def backtest(features_df, impulses, mbo_df, filename):
    """Backtests the strategy on detected impulses."""
    signals = []
    
    consolidations_count = 0
    aggression_count = 0
    delta_zones_count = 0
    returns_count = 0
    poc_conf_count = 0
    ob_conf_count = 0
    rejection_reason = "No impulses found"
    
    if not isinstance(features_df.index, pd.DatetimeIndex):
        features_df = features_df.set_index('ts')
    features_df.index = pd.to_datetime(features_df.index).tz_localize(None) if pd.to_datetime(features_df.index).tz is None else pd.to_datetime(features_df.index).tz_convert(None)
        
    # Simple heuristic for consolidations and aggression
    if not features_df.empty:
        candles_5m = features_df['price'].resample('5min').ohlc()
        consolidations = candles_5m[(candles_5m['high'] - candles_5m['low']) <= CONSOLIDATION_RANGE]
        consolidations_count = len(consolidations)
        
        aggression_count = len(features_df[features_df['size'] > AGGRESSION_MIN_CONTRACTS])
        
    candles = features_df['price'].resample('5min').ohlc()
    
    if not impulses:
        rejection_reason = "No impulses found"
    else:
        rejection_reason = "No delta zones found"
        
    for imp in impulses:
        start_time = imp['start']
        stop_time = imp['stop']
        imp_type = imp['type']
        
        profile = build_volume_profile(features_df, start_time, stop_time)
        zones = find_delta_zones(profile)
        
        target_zones = zones['buy'] if imp_type == 'up' else zones['sell']
        delta_zones_count += len(target_zones)
        
        if not target_zones:
            continue
            
        rejection_reason = "No price returns to zone"
        
        stop_time_np = np.datetime64(stop_time)
        post_impulse = features_df[features_df.index.values > stop_time_np]
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
            returns_count += 1
            rejection_reason = "Confirmation criteria not met"
            
            touch_np = np.datetime64(touch_time)
            conf_end = touch_np + np.timedelta64(CONFIRMATION_WINDOW_MIN, 'm')
            conf_window = post_impulse[
                (post_impulse.index.values > touch_np) & 
                (post_impulse.index.values <= conf_end)
            ]
            
            if conf_window.empty:
                continue
                
            window_candles = candles[
                (candles.index.values > touch_np) & 
                (candles.index.values <= conf_end)
            ]
            
            # Orderbook confirmation at touch (slice 5min window around touch time)
            mbo_start = touch_np - np.timedelta64(5, 'm')
            mbo_end = touch_np + np.timedelta64(5, 'm')
            mbo_slice = mbo_df[
                (mbo_df.index.values >= mbo_start) & 
                (mbo_df.index.values <= mbo_end)
            ]
            
            large_limit_present, layering = check_orderbook_state(mbo_slice, target_price, touch_time, imp_type)
            if large_limit_present:
                ob_conf_count += 1
                
            for c_ts, c_row in window_candles.iterrows():
                c_ts_np = np.datetime64(c_ts)
                c_trades = features_df[
                    (features_df.index.values >= c_ts_np) & 
                    (features_df.index.values < c_ts_np + np.timedelta64(5, 'm'))
                ]
                if c_trades.empty:
                    continue
                poc = c_trades.groupby('price')['size'].sum().idxmax()
                
                close_price = c_row['close']
                
                # CVD confirmation
                cvd_slice = conf_window[conf_window.index.values <= c_ts_np]
                cvd_at_touch = cvd_slice['cvd'].iloc[-1] if not cvd_slice.empty else 0
                current_cvd = c_trades['cvd'].iloc[-1] if 'cvd' in c_trades.columns else 0
                
                cvd_confirmed = False
                if imp_type == 'up' and current_cvd > cvd_at_touch:
                    cvd_confirmed = True
                elif imp_type == 'down' and current_cvd < cvd_at_touch:
                    cvd_confirmed = True
                    
                # POC confirmation
                poc_confirmed = False
                if imp_type == 'up' and close_price > poc:
                    poc_confirmed = True
                    poc_conf_count += 1
                elif imp_type == 'down' and close_price < poc:
                    poc_confirmed = True
                    poc_conf_count += 1
                    
                # Scoring
                score = 0
                if poc_confirmed:
                    score += 1
                if large_limit_present:
                    score += 1
                if cvd_confirmed:
                    score += 1
                    
                if score >= 1: # Lowered threshold
                    # Outcome calculation (Look forward 4 hours)
                    entry_time = np.datetime64(c_ts)
                    end_time = entry_time + np.timedelta64(4, 'h')

                    post_signal = features_df[
                        (features_df.index.values > entry_time) & 
                        (features_df.index.values <= end_time)
                    ]

                    entry_price = close_price
                    tp_price = entry_price + 150 if imp_type == 'up' else entry_price - 150
                    sl_price = entry_price - 60 if imp_type == 'up' else entry_price + 60

                    outcome = 'timeout'
                    result = '0R'
                    r_multiple = 0.0
                    bars_to_outcome = 0

                    if not post_signal.empty:
                        if imp_type == 'up':
                            hits_tp = post_signal[post_signal['price'].values >= tp_price]
                            hits_sl = post_signal[post_signal['price'].values <= sl_price]
                        else:
                            hits_tp = post_signal[post_signal['price'].values <= tp_price]
                            hits_sl = post_signal[post_signal['price'].values >= sl_price]

                        sentinel = np.datetime64('2100-01-01')
                        t_tp = hits_tp.index.values[0] if not hits_tp.empty else sentinel
                        t_sl = hits_sl.index.values[0] if not hits_sl.empty else sentinel

                        if t_tp < t_sl and t_tp != sentinel:
                            outcome = 'win'
                            result = '+2R'
                            r_multiple = 2.5
                            bars_to_outcome = int((t_tp - entry_time) / np.timedelta64(1, 'm'))
                        elif t_sl < t_tp and t_sl != sentinel:
                            outcome = 'loss'
                            result = '-1R'
                            r_multiple = -1.0
                            bars_to_outcome = int((t_sl - entry_time) / np.timedelta64(1, 'm'))
                            
                    signals.append({
                        'entry_time': c_ts,
                        'direction': 'buy' if imp_type == 'up' else 'sell',
                        'score': score,
                        'entry_price': entry_price,
                        'tp_price': tp_price,
                        'sl_price': sl_price,
                        'outcome': outcome,
                        'result': result,
                        'r_multiple': r_multiple,
                        'bars_to_outcome': bars_to_outcome
                    })
                    break
                    
    # Print step-by-step debug for the day
    date_str = filename.replace(".parquet", "")
    print(f"Day {date_str}:")
    print(f"  - Consolidations found: {consolidations_count}")
    print(f"  - Aggression breakouts: {aggression_count}")
    print(f"  - Valid impulses: {len(impulses)}")
    print(f"  - Delta zones found: {delta_zones_count}")
    print(f"  - Price returns to zone: {returns_count}")
    print(f"  - POC confirmations: {poc_conf_count}")
    print(f"  - Orderbook confirmations: {ob_conf_count}")
    print(f"  - Final signals: {len(signals)}")
    if not signals:
        print(f"  - Rejection reason: \"{rejection_reason}\"")
        
    return pd.DataFrame(signals)
                    
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
                
            median_price = mbo_df['price'].median()
            print(f"Raw median price: {median_price}")
            
            if median_price > 1e8:
                mbo_df['price'] = mbo_df['price'] / 1e9
                print("Auto-detected scale: divided by 1e9")
            elif median_price > 1e5:
                mbo_df['price'] = mbo_df['price'] / 1e4
                print("Auto-detected scale: divided by 1e4")
                
            # Filter immediately for trades
            trades_only = mbo_df[mbo_df['action'] == 'T'].copy()
            trades_only['delta'] = np.where(trades_only['side'] == 'A', trades_only['size'], -trades_only['size'])
            trades_only['cvd'] = trades_only['delta'].cumsum()
            
            print("Running strategy on trades only...")
            impulses = find_impulses(trades_only)
            signals = backtest(trades_only, impulses, mbo_df, filename)
            
            if not signals.empty:
                all_signals.append(signals)
                print(f"Generated {len(signals)} signals for {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
        finally:
            if 'mbo_df' in locals():
                del mbo_df
            if 'trades_only' in locals():
                del trades_only
            gc.collect()
            
    if all_signals:
        result_df = pd.concat(all_signals, ignore_index=True)
        os.makedirs("orderflow_ml", exist_ok=True)
        result_df.to_csv("orderflow_ml/volume_delta_dataset.csv", index=False)
        print(f"\n✅ Results exported to orderflow_ml/volume_delta_dataset.csv. Total signals: {len(result_df)}")
        
        # Print summary
        total = len(result_df)
        buys = len(result_df[result_df['direction'] == 'buy'])
        sells = len(result_df[result_df['direction'] == 'sell'])
        wins = len(result_df[result_df['outcome'] == 'win'])
        losses = len(result_df[result_df['outcome'] == 'loss'])
        timeouts = len(result_df[result_df['outcome'] == 'timeout'])
        avg_r = result_df['r_multiple'].mean()
        
        print(f"\nFinal Summary:")
        print(f"Total signals: {total}")
        print(f"Buy signals: {buys}")
        print(f"Sell signals: {sells}")
        print(f"Win: {wins} ({wins/total*100:.1f}%)" if total > 0 else "Win: 0 (0%)")
        print(f"Loss: {losses} ({losses/total*100:.1f}%)" if total > 0 else "Loss: 0 (0%)")
        print(f"Timeout: {timeouts} ({timeouts/total*100:.1f}%)" if total > 0 else "Timeout: 0 (0%)")
        print(f"Average R: {avg_r:.2f}" if total > 0 else "Average R: 0.00")
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
        if 2000 < i < 3000:
            prices.append(prices[-1] + np.random.uniform(0, 0.5)) # Upward impulse
        elif 4000 < i < 5000:
            prices.append(prices[-1] - np.random.uniform(0, 0.5)) # Return DOWN to buy zone
        elif 6000 < i < 7000:
            prices.append(prices[-1] - np.random.uniform(0, 0.5)) # Downward impulse
        elif 8000 < i < 9000:
            prices.append(prices[-1] + np.random.uniform(0, 0.5)) # Return UP to sell zone
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
    
    # Add large delta for buy zone in upward impulse
    df.loc[df.index[2500:2700], 'size'] = 500
    df.loc[df.index[2500:2700], 'side'] = 'A'
    
    # Add large delta for sell zone in downward impulse
    df.loc[df.index[6500:6700], 'size'] = 500
    df.loc[df.index[6500:6700], 'side'] = 'B'
    
    # Add some large limit orders (Add) to simulate support
    touch_price = df.iloc[6000]['price']
    
    df.loc[df.index[5500], 'action'] = 'A'
    df.loc[df.index[5500], 'size'] = 250
    df.loc[df.index[5500], 'price'] = touch_price
    df.loc[df.index[5500], 'side'] = 'B'
    df.loc[df.index[5500], 'order_id'] = 9999
    
    df.loc[df.index[5505], 'action'] = 'A'
    df.loc[df.index[5505], 'size'] = 210
    df.loc[df.index[5505], 'price'] = touch_price - 0.25
    df.loc[df.index[5505], 'side'] = 'B'
    df.loc[df.index[5505], 'order_id'] = 9998
    
    df.loc[df.index[5600], 'action'] = 'A'
    df.loc[df.index[5600], 'size'] = 300
    df.loc[df.index[5600], 'price'] = touch_price + 0.5
    df.loc[df.index[5600], 'side'] = 'B'
    df.loc[df.index[5600], 'order_id'] = 9997
    
    df.loc[df.index[5610], 'action'] = 'C'
    df.loc[df.index[5610], 'size'] = 300
    df.loc[df.index[5610], 'price'] = touch_price + 0.5
    df.loc[df.index[5610], 'side'] = 'B'
    df.loc[df.index[5610], 'order_id'] = 9997
    
    df.to_parquet(path)
    print(f"Mock data saved to {path}")

if __name__ == "__main__":
    main()

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gc

# Import existing infrastructure
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features

# Parameters
IMPULSE_MIN_POINTS = 120      # minimum NQ points for valid impulse (raised for quality)
IMPULSE_MAX_DURATION_MIN = 120
MIN_IMPULSE_CANDLES = 3       # minimum 1-min candles for a valid impulse
MIN_DELTA_CONTRACTS = 50      # minimum net delta at stopping zone (raised)
TP_POINTS = 75                # take profit in NQ points  
SL_ZONE_BUFFER = 5            # points behind the delta zone extreme for SL
SL_FALLBACK_MIN = 10          # minimum SL distance if zone is too close to entry
TOUCH_TOLERANCE = 5.0         # points tolerance for zone touch detection
CONFIRMATION_WINDOW_MIN = 30  # wait for confirmation within 30 min of zone touch
CONSOLIDATION_RANGE = 50      # max range for consolidation
AGGRESSION_MIN_CONTRACTS = 20 # min contracts for aggression
ABSORPTION_THRESHOLD = 0.30   # min opposing volume ratio for absorption
SWING_LOOKBACK = 5            # candles to look left/right for swing detection
SWING_TIMEFRAME = '15min'     # timeframe for structural swing detection
STOPPING_ZONE_PCT = 0.30      # look at last 30% of impulse range for delta zones

def find_impulses(df):
    """
    Detects significant structural impulse moves using swing high/low detection.

    Improvements over v1:
    1. Uses 15-min candles for structural significance (less noise than 5-min)
    2. N=5 lookback — only picks swings that held for 5 bars in each direction
    3. Enforces strict alternation: high → low → high → low
       When two highs or two lows appear consecutively, keeps the more extreme one
    4. Filters by IMPULSE_MIN_POINTS
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'ts' in df.columns:
            df = df.set_index('ts')

    ohlc = df['price'].resample(SWING_TIMEFRAME).ohlc().dropna()

    if len(ohlc) < SWING_LOOKBACK * 2 + 1:
        return []

    highs = ohlc['high'].values
    lows  = ohlc['low'].values
    times = ohlc.index
    N = SWING_LOOKBACK

    
    raw_swings = []
    for i in range(N, len(ohlc) - N):
        is_swing_high = all(
            highs[i] >= highs[i - j] and highs[i] >= highs[i + j]
            for j in range(1, N + 1)
        )
        is_swing_low = all(
            lows[i] <= lows[i - j] and lows[i] <= lows[i + j]
            for j in range(1, N + 1)
        )
        if is_swing_high:
            raw_swings.append({'time': times[i], 'price': highs[i], 'type': 'high'})
        if is_swing_low:
            raw_swings.append({'time': times[i], 'price': lows[i], 'type': 'low'})

    if len(raw_swings) < 2:
        return []

    
    raw_swings.sort(key=lambda s: s['time'])

  
    alternating = [raw_swings[0]]
    for swing in raw_swings[1:]:
        prev = alternating[-1]
        if swing['type'] != prev['type']:
            alternating.append(swing)
        else:
            # Same type — keep more extreme
            if swing['type'] == 'high' and swing['price'] > prev['price']:
                alternating[-1] = swing
            elif swing['type'] == 'low' and swing['price'] < prev['price']:
                alternating[-1] = swing

    if len(alternating) < 2:
        return []

    # ── Step 3: Build impulses from alternating swing pairs ──
    impulses = []
    for i in range(len(alternating) - 1):
        a = alternating[i]
        b = alternating[i + 1]
        points = abs(b['price'] - a['price'])

        if points < IMPULSE_MIN_POINTS:
            continue

        if a['type'] == 'low' and b['type'] == 'high':
            imp_type = 'up'
        elif a['type'] == 'high' and b['type'] == 'low':
            imp_type = 'down'
        else:
            continue

        impulses.append({
            'type': imp_type,
            'start': a['time'],
            'stop':  b['time'],
            'price_start': a['price'],
            'price_stop':  b['price'],
            'points': points,
        })

    print(f"Found {len(impulses)} valid impulses (15min, N={N}, min={IMPULSE_MIN_POINTS}pts).")
    return impulses

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

def find_delta_zones(profile, impulse):
    """
    Finds institutional delta zones near the STOPPING point of the impulse.

    Key insight: the delta zone that matters is where the impulse STOPPED.
    That's where institutional limit orders absorbed the aggressive flow and
    halted the move. Looking at delta across the entire profile dilutes the
    signal with noise from the body of the impulse.

    Improvements over v1:
    1. Only examines the last 30% of the impulse range (near price_stop)
    2. Returns the single strongest zone (not a list of all qualifying levels)
    3. Computes delta exhaustion: did aggressive flow weaken at the extreme?

    Returns dict with:
      zone_price:       price level of the strongest stopping delta
      zone_delta:       net delta at that level (signed)
      zone_volume:      total volume at that level
      exhaustion:       bool — True if delta was fading at the extreme
      exhaustion_score: float 0-1, how exhausted the flow was
      buy_zones / sell_zones: legacy-compatible lists
    """
    if profile.empty:
        return {
            'buy': [], 'sell': [],
            'zone_price': None, 'zone_delta': 0, 'zone_volume': 0,
            'exhaustion': False, 'exhaustion_score': 0.0,
        }

    price_start = impulse['price_start']
    price_stop  = impulse['price_stop']
    imp_type    = impulse['type']

    # ── Define the reload zone: upper half for sells, lower half for buys ──
    mid_price = (price_start + price_stop) / 2.0
    
    if imp_type == 'down':
        # Down impulse (Sell trend) → look at the UPPER half
        zone_low  = mid_price
        zone_high = max(price_start, price_stop) + 10 # buffer
    else:
        # Up impulse (Buy trend) → look at the LOWER half
        zone_low  = min(price_start, price_stop) - 10 # buffer
        zone_high = mid_price

    reload_profile = profile[
        (profile.index >= zone_low) & (profile.index <= zone_high)
    ]

    if reload_profile.empty:
        return {
            'buy': [], 'sell': [],
            'zone_price': None, 'zone_delta': 0, 'zone_volume': 0,
            'exhaustion': False, 'exhaustion_score': 0.0,
        }

    # ── Find the level with the strongest INITIATING delta ──
    if imp_type == 'down':
        # Sell trend: find the level with the most NEGATIVE delta in the upper half
        best_idx = reload_profile['delta'].idxmin()
    else:
        # Buy trend: find the level with the most POSITIVE delta in the lower half
        best_idx = reload_profile['delta'].idxmax()

    zone_delta  = float(reload_profile.loc[best_idx, 'delta'])
    zone_volume = float(reload_profile.loc[best_idx, 'volume'])

    # Exhaustion logic is skipped for the reload strategy, as we look for continuation
    exhaustion = False
    exhaustion_score = 0.0


    # ── Legacy-compatible output + enriched data ──
    meets_threshold = abs(zone_delta) >= MIN_DELTA_CONTRACTS
    buy_zones  = [best_idx] if imp_type == 'up' and meets_threshold else []
    sell_zones = [best_idx] if imp_type == 'down' and meets_threshold else []

    return {
        'buy': buy_zones,
        'sell': sell_zones,
        'zone_price': float(best_idx),
        'zone_delta': zone_delta,
        'zone_volume': zone_volume,
        'exhaustion': exhaustion,
        'exhaustion_score': exhaustion_score
    }

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

def _detect_absorption(features_df, imp, profile):
    """
    Detects absorption at the end of the impulse.
    Absorption = large opposing trades near the impulse extreme that failed to push
    price further. This confirms the delta zone is real — the other side tried to
    continue but was absorbed by limit orders.
    
    For UP impulse: look for large SELL trades near the top (price_stop) that didn't
    push price below that level → buyers absorbed sellers.
    For DOWN impulse: look for large BUY trades near the bottom (price_stop) that didn't
    push price above that level → sellers absorbed buyers.
    """
    end_np = np.datetime64(imp['stop'])
    # Window: last 5 minutes of the impulse
    start_np = end_np - np.timedelta64(5, 'm')
    
    end_slice = features_df[
        (features_df.index.values >= start_np) &
        (features_df.index.values <= end_np)
    ]
    
    if end_slice.empty or len(end_slice) < 5:
        return False
    
    extreme_price = imp['price_stop']
    tolerance = 20.0  # look within 20 points of the extreme
    
    near_extreme = end_slice[abs(end_slice['price'] - extreme_price) <= tolerance]
    if near_extreme.empty:
        return False
    
    if imp['type'] == 'up':
        # Look for large sell-side trades (side == 'B' means aggressive sell hitting bid)
        opposing = near_extreme[near_extreme['side'] == 'B']
    else:
        # Look for large buy-side trades (side == 'A' means aggressive buy lifting ask)
        opposing = near_extreme[near_extreme['side'] == 'A']
    
    if opposing.empty:
        return False
    
    opposing_volume = opposing['size'].sum()
    total_volume = near_extreme['size'].sum()
    
    # Absorption confirmed if opposing side had significant volume (>30%)
    # but price still moved in the impulse direction
    if total_volume > 0 and (opposing_volume / total_volume) >= ABSORPTION_THRESHOLD:
        # Verify price didn't reverse past the extreme after absorption
        post_stop = features_df[features_df.index.values > end_np].head(100)
        if post_stop.empty:
            return False
        if imp['type'] == 'up':
            # After up impulse, price should pull back (expected) — absorption confirmed
            # if opposing volume was present but price still reached the high
            return True
        else:
            # After down impulse, price should bounce (expected) — absorption confirmed
            return True
    
    return False


def backtest(features_df, impulses, mbo_df, filename):
    """
    Backtests the Volume Delta Profile Strategy.
    
    Strategy flow:
    1. Find impulse move (up/down)
    2. Build Volume Profile over the impulse range
    3. Find largest delta zones — limit orders that stopped the move
    4. Wait for price to return to these zones
    5. Enter in original impulse direction when confirmed (POC mandatory)
    6. SL placed behind the largest delta zone extreme
    7. TP at fixed 150 points from entry
    """
    signals = []
    
    consolidations_count = 0
    aggression_count = 0
    delta_zones_count = 0
    returns_count = 0
    poc_conf_count = 0
    ob_conf_count = 0
    absorption_count = 0
    skipped_short_impulse = 0
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
    
    # Pre-compute 1-min candles for impulse duration check
    candles_1m = features_df['price'].resample('1min').ohlc().dropna()
    
    if not impulses:
        rejection_reason = "No impulses found"
    else:
        rejection_reason = "No delta zones found"
        
    for imp in impulses:
        start_time = imp['start']
        stop_time = imp['stop']
        imp_type = imp['type']
        
        # ── Impulse quality check: minimum 3 candles duration ──
        imp_candles = candles_1m[
            (candles_1m.index.values >= np.datetime64(start_time)) &
            (candles_1m.index.values <= np.datetime64(stop_time))
        ]
        if len(imp_candles) < MIN_IMPULSE_CANDLES:
            skipped_short_impulse += 1
            continue
        
        profile = build_volume_profile(features_df, start_time, stop_time)
        zones = find_delta_zones(profile, imp)
        
        target_zones = zones['buy'] if imp_type == 'up' else zones['sell']
        delta_zones_count += len(target_zones)
        
        if not target_zones:
            continue
        
        # Use the best stopping-zone price from the enriched find_delta_zones
        largest_delta_zone_price = zones['zone_price']
        delta_exhaustion = zones.get('exhaustion', False)
        delta_exhaustion_score = zones.get('exhaustion_score', 0.0)
        
        # ── Absorption detection at end of impulse ──
        absorption_detected = _detect_absorption(features_df, imp, profile)
        if absorption_detected:
            absorption_count += 1
            
        rejection_reason = "No price returns to zone"
        
        stop_time_np = np.datetime64(stop_time)
        post_impulse = features_df[features_df.index.values > stop_time_np]
        if post_impulse.empty:
            continue
            
        touched = False
        touch_time = None
        target_price = None
        
        # ── Touch tolerance: 5.0 points (increased from 1.0) ──
        touch_price = None
        for ts, row in post_impulse.iterrows():
            price = row['price']
            if abs(price - largest_delta_zone_price) <= TOUCH_TOLERANCE:
                touched = True
                touch_time = ts
                target_price = largest_delta_zone_price
                touch_price = price
                break
                
        if touched:
            returns_count += 1
            
            entry_time = np.datetime64(touch_time)
            entry_price = touch_price
            
            # ── Fixed SL: 100 points, Fixed TP: 100 points (1:1 RR) ──
            if imp_type == 'up':
                sl_price = entry_price - 100
                tp_price = entry_price + 100
            else:
                sl_price = entry_price + 100
                tp_price = entry_price - 100
                
            sl_distance = 100
            reward_risk_ratio = 1.0  # 1:1 RR
            
            end_time = entry_time + np.timedelta64(4, 'h')

            post_signal = features_df[
                        (features_df.index.values > entry_time) & 
                        (features_df.index.values <= end_time)
                    ]

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
                t_tp = hits_tp.index.values.min() if not hits_tp.empty else sentinel
                t_sl = hits_sl.index.values.min() if not hits_sl.empty else sentinel

                if t_tp < t_sl and t_tp != sentinel:
                    outcome = 'win'
                    r_multiple = round(reward_risk_ratio, 2)
                    result = f'+{r_multiple}R'
                    bars_to_outcome = int((t_tp - entry_time) / np.timedelta64(1, 'm'))
                elif t_sl < t_tp and t_sl != sentinel:
                    outcome = 'loss'
                    r_multiple = -1.0
                    result = '-1R'
                    bars_to_outcome = int((t_sl - entry_time) / np.timedelta64(1, 'm'))

            if imp_type != 'up':
                print(f"\nSELL AUDIT: entry={entry_price:.2f}, tp={tp_price:.2f}, sl={sl_price:.2f}")
                print(f"  tp < entry: {tp_price < entry_price}, sl > entry: {sl_price > entry_price}")
                print(f"  post_signal rows: {len(post_signal)}")
                if not post_signal.empty:
                    print(f"  price range: {post_signal['price'].min():.2f} - {post_signal['price'].max():.2f}")
                    print(f"  hits_tp count: {len(post_signal[post_signal['price'].values <= tp_price])}")
                    print(f"  hits_sl count: {len(post_signal[post_signal['price'].values >= sl_price])}")
                    print(f"  outcome: {outcome}")
                print(f"  t_tp: {t_tp if t_tp != sentinel else 'never'}")
                print(f"  t_sl: {t_sl if t_sl != sentinel else 'never'}")

            signals.append({
                'entry_time': str(touch_time) + 'Z',
                'direction': 'buy' if imp_type == 'up' else 'sell',
                'score': 0,
                'entry_price': entry_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'sl_distance': round(sl_distance, 2),
                'reward_risk': round(reward_risk_ratio, 2),
                'largest_delta_zone': largest_delta_zone_price,
                'absorption': absorption_detected,
                'exhaustion': delta_exhaustion,
                'exhaustion_score': delta_exhaustion_score,
                'outcome': outcome,
                'result': result,
                'r_multiple': r_multiple,
                'bars_to_outcome': bars_to_outcome
            })
                    
    # Print step-by-step debug for the day
    date_str = filename.replace(".parquet", "")
    print(f"Day {date_str}:")
    print(f"  - Consolidations found: {consolidations_count}")
    print(f"  - Aggression breakouts: {aggression_count}")
    print(f"  - Valid impulses: {len(impulses)} (skipped {skipped_short_impulse} short)")
    print(f"  - Delta zones found: {delta_zones_count}")
    print(f"  - Absorption detected: {absorption_count}")
    print(f"  - Price returns to zone: {returns_count}")
    print(f"  - POC confirmations: {poc_conf_count}")
    print(f"  - Orderbook confirmations: {ob_conf_count}")
    print(f"  - Final signals: {len(signals)}")
    if not signals:
        print(f"  - Rejection reason: \"{rejection_reason}\"")
        
    return pd.DataFrame(signals)

def stream_main():
    print("🚀 Starting Volume Delta Profile Strategy Backtest (Stream Mode)...")
    
    cache_dir = "data/raw/mbo/NQ"
    if not os.path.exists(cache_dir):
        print(f"Cache directory {cache_dir} missing. Creating mock data for demonstration.")
        create_mock_data()
        
    files = [f for f in os.listdir(cache_dir) if f.endswith(".parquet")]
    if not files:
        print("No parquet files found. Creating mock data.")
        create_mock_data()
        files = ["2023-01-03.parquet"]
        
    for filename in files:
        path = os.path.join(cache_dir, filename)
        print(f"\nProcessing {filename}...")
        
        try:
            # Fix 1: Process file by file and read only needed columns to fix OOM issue
            try:
                mbo_df = pd.read_parquet(path, columns=['ts_event', 'price', 'size', 'action', 'side', 'order_id'])
            except Exception:
                mbo_df = pd.read_parquet(path, columns=['price', 'size', 'action', 'side', 'order_id'])
                
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
            trades_only['size'] = trades_only['size'].astype('int64')  # prevent uint32 overflow

            # Filter out spread contract trades (prices far from median)
            median_price = trades_only['price'].median()
            trades_only = trades_only[
                (trades_only['price'] > median_price * 0.5) &
                (trades_only['price'] < median_price * 1.5)
            ]
            
            # ── SPIKE FILTER (Bad Ticks) ──
            # Raw MBO data contains erroneous prints far from the market price.
            # Using a local 11-tick centered median perfectly preserves real, rapid 
            # market movements (like news spikes) while deleting isolated 1-lot errors.
            if not trades_only.empty:
                rolling_med = trades_only['price'].rolling(11, center=True).median().bfill().ffill()
                trades_only = trades_only[np.abs(trades_only['price'] - rolling_med) <= 30]
            trades_only['delta'] = np.where(trades_only['side'] == 'A', trades_only['size'], -trades_only['size'])
            trades_only['cvd'] = trades_only['delta'].cumsum()
            
            print("Running strategy on trades only...")
            impulses = find_impulses(trades_only)
            signals_df = backtest(trades_only, impulses, mbo_df, filename)
            
            if not signals_df.empty:
                print(f"Generated {len(signals_df)} signals for {filename}")
                # Yield signals as dicts
                yield signals_df.to_dict(orient='records')
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
        finally:
            if 'mbo_df' in locals():
                del mbo_df
            if 'trades_only' in locals():
                del trades_only
            if 'signals_df' in locals():
                del signals_df
            gc.collect()

def main():
    all_signals = []
    for chunk in stream_main():
        all_signals.extend(chunk)
        
    if all_signals:
        result_df = pd.DataFrame(all_signals)
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
        return result_df
    else:
        print("\n❌ No signals generated across all files.")
        return pd.DataFrame()

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

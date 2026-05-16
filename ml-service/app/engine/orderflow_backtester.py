import pandas as pd
import numpy as np
import os
from app.engine.auto_edge import edge_validator
from app.engine.regime import detect_market_regime


def calculate_session_profile(events_df: pd.DataFrame):
    """Calculates POC, VAH, and VAL from the volume profile."""
    if events_df.empty:
        return None, None, None
    try:
        # Group volume by price bins
        bins = 50
        profile = events_df.groupby(pd.cut(events_df["price"], bins=bins))["size"].sum()
        poc_interval = profile.idxmax()
        poc = poc_interval.mid if pd.notna(poc_interval) else events_df["price"].iloc[0]

        # Calculate Value Area (70%)
        total_vol = profile.sum()
        sorted_profile = profile.sort_values(ascending=False)
        cum_vol = sorted_profile.cumsum()
        value_area = sorted_profile[cum_vol <= total_vol * 0.70]

        if not value_area.empty:
            vah = value_area.index.categories.max().right
            val = value_area.index.categories.min().left
        else:
            vah = events_df["price"].max()
            val = events_df["price"].min()

        return poc, vah, val
    except:
        return (
            events_df["price"].mean(),
            events_df["price"].max(),
            events_df["price"].min(),
        )


def get_prev_day_profile(current_date_str: str) -> tuple:
    import os
    from datetime import datetime, timedelta

    # Найти предыдущий файл в кэше
    cache_dir = "data/raw/mbo/NQ"
    files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".parquet")])
    dates = [f.replace(".parquet", "") for f in files]

    if current_date_str not in dates:
        return None, None, None

    idx = dates.index(current_date_str)
    if idx == 0:
        # Previous file not in cache - skip instead of fetching
        print(f"⚠️ Previous day profile missing for {current_date_str}. Skipping bias calculation from prev day.")
        return None, None, None

    prev_date = dates[idx - 1]
    prev_path = f"{cache_dir}/{prev_date}.parquet"

    prev_df = pd.read_parquet(prev_path)

    # Фильтр NY сессии
    ts_col = "ts_event" if "ts_event" in prev_df.columns else "ts"
    prev_df[ts_col] = pd.to_datetime(prev_df[ts_col], utc=True)

    ny = prev_df[
        (
            prev_df[ts_col].dt.tz_convert("US/Eastern").dt.time
            >= pd.to_datetime("09:30").time()
        )
        & (
            prev_df[ts_col].dt.tz_convert("US/Eastern").dt.time
            < pd.to_datetime("16:00").time()
        )
    ]

    # Фильтр аномалий
    if "-" in prev_df.columns.tolist() or "symbol" in prev_df.columns:
        ny = ny[
            ~ny.get("symbol", pd.Series([""] * len(ny))).str.contains("-", na=False)
        ]

    q1 = ny["price"].quantile(0.01)
    q99 = ny["price"].quantile(0.99)
    ny = ny[(ny["price"] >= q1) & (ny["price"] <= q99)]

    return calculate_session_profile(ny)


def run_l3_backtest(
    events_df: pd.DataFrame,
    filter_signals: bool = True,
    use_validated_edge: bool = True,
) -> dict:
    """
    FABIO VALENTINO MODEL v2.0
    - STEP 0: Daily Bias (Hard Filter)
    - STEP 1: Market State
    - STEP 2: Location (POC Target)
    - STEP 3: Context Patterns
    - STEP 4: Aggression (Entry Trigger)
    - STEP 5: Execution (Scaling, Target = POC)
    """
    if events_df.empty:
        return {
            "trades": [],
            "stats": {"total_trades": 0, "win_rate": 0, "avg_score": 0},
        }

    trades = []
    in_position = False

    if use_validated_edge:
        edge_validator.validate_all_edges()

    regime = detect_market_regime(events_df)
    regime_type = regime["regime_type"]

    # STEP 0: Calculate Session Bias
    current_date_str = (
        events_df.iloc[0]["ts"].strftime("%Y-%m-%d") if not events_df.empty else None
    )
    poc, vah, val = (
        get_prev_day_profile(current_date_str)
        if current_date_str
        else (None, None, None)
    )
    if poc is None:
        poc, vah, val = calculate_session_profile(events_df)

    # print(f"DEBUG: poc={poc}, vah={vah}, val={val}")

    daily_pnl = 0.0  # Track PnL for scaling
    daily_loss_pct = 0.0  # A1: Максимальный дневной убыток
    current_day = events_df.iloc[0]["ts"].date() if not events_df.empty else None
    daily_loss_limit_hit = False

    bias_state = {
        "direction": "neutral",
        "updated_at": None,
        "cooldown_until": None,
        "pending_context": [],
    }

    pending_context = None  # STATE MACHINE: Track context waiting for aggression
    first_impulse_seen = False

    # COOLDOWN & LEVEL TRACKING
    last_trade_time = None
    traded_levels = set()

    # SESSION MONTH
    month = events_df.iloc[0]["ts"].month
    summer_months = [5, 6, 7, 8]

    # FUNNEL STATS (Full Diagnostics)
    funnel = {
        "total_events": len(events_df),
        "blocked_session_time": 0,
        "blocked_unclear": 0,
        "blocked_bias_cooldown": 0,
        "blocked_boundary": 0,
        "passed_boundary": 0,
        "blocked_bias_match": 0,
        "passed_bias_match": 0,
        "blocked_structural_invalidation": 0,
        "blocked_retest_zone": 0,
        "blocked_aggression_impulse": 0,
        "passed_aggression": 0,
        "blocked_internal_poc": 0,
        "passed_internal_poc": 0,
        "blocked_score_threshold": 0,
        "passed_score": 0,
        "blocked_direction_mismatch": 0,
        "blocked_edge_validator": 0,
        "passed_edge": 0,
        "blocked_rr_too_low": 0,
        "blocked_trade_cooldown": 0,
        "cooldown_strict_rejections": 0,
        "cooldown_relaxed_saves": 0,
        "cooldown_bypass_high_score": 0,
        "internal_poc_strict_pass": 0,
        "relaxed_poc_saves": 0,
    }
    events_list = events_df.to_dict("records")
    total_events = len(events_list)
    for i, row in enumerate(events_list):
        if i % 50000 == 0:
            print(f"🔄 Processed {i}/{total_events} events...")

        # Time and Session
        row_ts = pd.to_datetime(row["ts"])
        if row_ts.tz is None:
            row_ts = row_ts.tz_localize("UTC")
        ny_time = row_ts.tz_convert("US/Eastern")
        row_date = ny_time.date()

        # Reset daily variables if new day
        if row_date != current_day:
            current_day = row_date
            daily_pnl = 0.0
            daily_loss_pct = 0.0
            daily_loss_limit_hit = False
            traded_levels.clear()
            pending_context = None

        if daily_loss_pct >= 0.02:
            daily_loss_limit_hit = True

        if in_position:
            trade = trades[-1]

            # B2: Закрытие позиций до конца сессии
            if ny_time.time() >= pd.to_datetime("15:45").time():
                trade["exit_price"] = row["price"]
                trade["result"] = (
                    "loss"
                    if (
                        trade["direction"] == "buy"
                        and row["price"] < trade["entry_price"]
                    )
                    or (
                        trade["direction"] == "sell"
                        and row["price"] > trade["entry_price"]
                    )
                    else "win"
                    if (
                        trade["direction"] == "buy"
                        and row["price"] > trade["entry_price"]
                    )
                    or (
                        trade["direction"] == "sell"
                        and row["price"] < trade["entry_price"]
                    )
                    else "be"
                )
                trade["exit_reason"] = "session_end"
                sign = 1 if trade["direction"] == "buy" else -1
                trade["r_multiple"] = (
                    sign
                    * (row["price"] - trade["entry_price"])
                    / abs(trade["entry_price"] - trade["original_stop"])
                )
                trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                trade["exit_time"] = row["ts"]
                trade["early_exit"] = True
                daily_pnl += trade["outcome_R"]
                # НЕ добавлять к daily_loss_pct при session_end
                in_position = False
                continue

            # Early exit logic: Opposite Aggression with Follow-Through
            exit_early = False
            is_ny = (
                pd.to_datetime("09:30").time()
                <= ny_time.time()
                < pd.to_datetime("16:00").time()
            )
            session_min_contracts = 15 if is_ny else 10

            vol_size = row.get("size", 0)
            is_big_trade_now = vol_size >= session_min_contracts
            current_event_dir = "buy" if row.get("delta", 0) > 0 else "sell"

            if is_big_trade_now and current_event_dir != trade["direction"]:
                # Opposite aggression detected! Check if price is moving against us
                if (
                    trade["direction"] == "buy"
                    and row["price"] < trade["entry_price"] - 0.5
                ):
                    exit_early = True  # Selling pressure + price dropping = EXIT
                elif (
                    trade["direction"] == "sell"
                    and row["price"] > trade["entry_price"] + 0.5
                ):
                    exit_early = True  # Buying pressure + price rising = EXIT

            # A3: Ранний выход при CVD дивергенции
            cvd_div = row.get("cvd_divergence", 0)  # Computed in Block D
            if trade["direction"] == "buy" and cvd_div == -1:
                exit_early = True
            elif trade["direction"] == "sell" and cvd_div == 1:
                exit_early = True

            # A2: Перенос в безубыток по CVD
            if not trade.get("be_triggered", False):
                risk_amt = abs(trade["entry_price"] - trade["stop"])
                price_moved = False
                cvd_push = False
                cvd_baseline = row.get("cvd_baseline", 50)

                if trade["direction"] == "buy":
                    price_moved = row["price"] >= trade["entry_price"] + risk_amt
                    cvd_push = (
                        row.get("cvd", 0) - trade.get("entry_cvd", 0) > cvd_baseline * 2
                    )
                else:
                    price_moved = row["price"] <= trade["entry_price"] - risk_amt
                    cvd_push = (
                        trade.get("entry_cvd", 0) - row.get("cvd", 0) > cvd_baseline * 2
                    )

                if price_moved and cvd_push:
                    trade["stop"] = trade["entry_price"]
                    trade["be_triggered"] = True

            if trade["direction"] == "buy":
                if row["price"] <= trade["stop"] or exit_early:
                    if row["price"] <= trade["stop"]:
                        trade["exit_price"] = trade["stop"]
                        trade["exit_reason"] = "stop"
                    else:
                        trade["exit_price"] = row["price"]
                        trade["exit_reason"] = "early_exit"

                    trade["result"] = (
                        "loss"
                        if trade["exit_price"] < trade["entry_price"]
                        else ("win" if trade["exit_price"] > trade["entry_price"] else "be")
                    )
                    trade["r_multiple"] = (
                        (trade["exit_price"] - trade["entry_price"])
                        / abs(trade["entry_price"] - trade["original_stop"])
                    )
                    trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                    # print(f"{trade['exit_reason'].upper()} HIT: entry={trade['entry_price']}, stop={trade['stop']}, exit_price={trade['exit_price']}, original_stop={trade['original_stop']}, r={trade['r_multiple']:.2f}")
                    trade["exit_time"] = row["ts"]
                    trade["early_exit"] = (trade["exit_reason"] == "early_exit")
                    trade["pnl_pts"] = trade["exit_price"] - trade["entry_price"]
                    daily_pnl += trade["outcome_R"]
                    if trade["result"] == "loss":
                        current_risk_pct = 0.0025
                        if trade.get("score", 0) == 4:
                            current_risk_pct = 0.005
                        elif trade.get("score", 0) >= 5:
                            current_risk_pct = 0.0075
                        daily_loss_pct += abs(trade["outcome_R"]) * current_risk_pct
                    in_position = False
                elif row["price"] >= trade["target"]:
                    trade["exit_price"] = trade["target"]
                    trade["result"] = "win"
                    trade["r_multiple"] = (
                        (trade["target"] - trade["entry_price"])
                        / abs(trade["entry_price"] - trade["original_stop"])
                    )
                    trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                    trade["exit_time"] = row["ts"]
                    trade["exit_reason"] = "target"
                    trade["pnl_pts"] = trade["target"] - trade["entry_price"]
                    daily_pnl += trade["outcome_R"]
                    in_position = False
            else:
                if row["price"] >= trade["stop"] or exit_early:
                    if row["price"] >= trade["stop"]:
                        trade["exit_price"] = trade["stop"]
                        trade["exit_reason"] = "stop"
                    else:
                        trade["exit_price"] = row["price"]
                        trade["exit_reason"] = "early_exit"

                    trade["result"] = (
                        "loss"
                        if trade["exit_price"] > trade["entry_price"]
                        else ("win" if trade["exit_price"] < trade["entry_price"] else "be")
                    )
                    trade["r_multiple"] = (
                        (trade["entry_price"] - trade["exit_price"])
                        / abs(trade["entry_price"] - trade["original_stop"])
                    )
                    trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                    # print(f"{trade['exit_reason'].upper()} HIT: entry={trade['entry_price']}, stop={trade['stop']}, exit_price={trade['exit_price']}, original_stop={trade['original_stop']}, r={trade['r_multiple']:.2f}")
                    trade["exit_time"] = row["ts"]
                    trade["early_exit"] = (trade["exit_reason"] == "early_exit")
                    trade["pnl_pts"] = trade["entry_price"] - trade["exit_price"]
                    daily_pnl += trade["outcome_R"]
                    if trade["result"] == "loss":
                        current_risk_pct = 0.0025
                        if trade.get("score", 0) == 4:
                            current_risk_pct = 0.005
                        elif trade.get("score", 0) >= 5:
                            current_risk_pct = 0.0075
                        daily_loss_pct += abs(trade["outcome_R"]) * current_risk_pct
                    in_position = False
                elif row["price"] <= trade["target"]:
                    trade["exit_price"] = trade["target"]
                    trade["result"] = "win"
                    trade["r_multiple"] = (
                        (trade["entry_price"] - trade["target"])
                        / abs(trade["entry_price"] - trade["original_stop"])
                    )
                    trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                    trade["exit_time"] = row["ts"]
                    trade["exit_reason"] = "target"
                    trade["pnl_pts"] = trade["entry_price"] - trade["target"]
                    daily_pnl += trade["outcome_R"]
                    in_position = False
            continue

        if daily_loss_limit_hit:
            continue

        # B1: Блокировка первых 20 минут NY и внесессионной торговли
        if (
            ny_time.time() >= pd.to_datetime("16:00").time()
            or ny_time.time() < pd.to_datetime("03:00").time()
        ):
            funnel["blocked_session_time"] += 1
            continue  # вне сессий: нет торговли

        is_ny_session = (
            pd.to_datetime("09:30").time()
            <= ny_time.time()
            < pd.to_datetime("16:00").time()
        )
        is_london_session = (
            pd.to_datetime("03:00").time()
            <= ny_time.time()
            < pd.to_datetime("09:30").time()
        )

        if is_ny_session and ny_time.time() < pd.to_datetime("09:50").time():
            # Заблокировать все входы до 09:50 ET
            if not in_position:
                continue

        # C3: UNCLEAR состояние
        current_price = row["price"]
        direction = "buy" if row.get("delta", 0) > 0 else "sell"
        cvd_slope = row.get("cvd_slope", 0)
        vp_std = row.get("vp_std", 100)
        vp_std_mean = row.get("vp_std_mean", 100)
        cvd_slope_std = row.get("cvd_slope_std", 10)
        inside_va = (val is not None and vah is not None) and (
            val < current_price < vah
        )
        cvd_unclear = abs(cvd_slope) < cvd_slope_std * 0.5
        profile_flat = vp_std < vp_std_mean * 0.7

        market_state = (
            "UNCLEAR" if (inside_va and cvd_unclear and profile_flat) else regime_type
        )
        if market_state == "UNCLEAR":
            funnel["blocked_unclear"] += 1
            continue

        # C2: Динамический байас
        if vah is not None and val is not None:
            if current_price > vah and bias_state["direction"] != "buy":
                bias_state["direction"] = "buy"
                bias_state["updated_at"] = row_ts
                bias_state["cooldown_until"] = row_ts + pd.Timedelta(minutes=5)
                pending_context = None
            elif current_price < val and bias_state["direction"] != "sell":
                bias_state["direction"] = "sell"
                bias_state["updated_at"] = row_ts
                bias_state["cooldown_until"] = row_ts + pd.Timedelta(minutes=5)
                pending_context = None

        bias = bias_state["direction"]

        if bias_state["cooldown_until"] and row_ts < bias_state["cooldown_until"]:
            funnel["blocked_bias_cooldown"] += 1
            continue  # Cooldown after bias shift

        event_type = row.get("event_type", "normal")

        # STEP 3: Context Pattern Detection
        atr = row.get("atr", 10)
        tolerance = atr * 3.0

        at_vah = vah is not None and abs(current_price - vah) <= tolerance
        at_val = val is not None and abs(current_price - val) <= tolerance

        if event_type in ["absorption", "trap", "breakout"] and (at_vah or at_val):
            funnel["passed_boundary"] += 1
            if bias == "buy":
                setup_direction = "buy" if at_vah else "buy"
            elif bias == "sell":
                setup_direction = "sell" if at_val else "sell"
            else:  # neutral
                setup_direction = "sell" if at_vah else "buy"

            bias_match = (
                (setup_direction == "buy" and bias == "buy")
                or (setup_direction == "sell" and bias == "sell")
                or bias == "neutral"
            )
            if bias_match:
                # C1: BREAKOUT vs TRAP
                if event_type == "breakout":
                    retest_zone = (
                        (vah - atr * 0.5, vah)
                        if setup_direction == "sell"
                        else (val, val + atr * 0.5)
                    )
                    pattern_type = "breakout"
                else:
                    retest_zone = None
                    pattern_type = event_type

                pending_context = {
                    "direction": setup_direction,
                    "type": pattern_type,
                    "lvn": current_price,
                    "invalidation_level": vah + atr
                    if setup_direction == "sell"
                    else val - atr,
                    "retest_zone": retest_zone,
                    "events_elapsed": 0,
                }
                # print(f"DEBUG Pending: dir={setup_direction}, type={pattern_type}, price={current_price}, bias={bias}")
                first_impulse_seen = False
                funnel["passed_bias_match"] += 1
            else:
                funnel["blocked_bias_match"] += 1
        else:
            funnel["blocked_boundary"] += 1

        # D2: Хард-фильтр контрактов
        vol_size = row.get("size", 0)
        is_tradable = (
            True  # фильтр по одной сделке убираем — объём уже агрегирован в features
        )

        # STEP 2: Pending Context Evaluation (Entry Trigger)
        if pending_context:
            if pending_context.get("created_at") is None:
                pending_context["created_at"] = row_ts
            time_elapsed = (row_ts - pending_context["created_at"]).total_seconds()

            # 1. Structural Invalidation
            invalidated = False
            if (
                pending_context["direction"] == "sell"
                and current_price > pending_context["invalidation_level"]
            ) or (
                pending_context["direction"] == "buy"
                and current_price < pending_context["invalidation_level"]
            ):
                invalidated = True

            if time_elapsed > 300:  # 5 минут максимум
                invalidated = True

            if invalidated:
                funnel["blocked_structural_invalidation"] += 1
                pending_context = None
                continue

            # If breakout, check if price is in retest_zone
            if pending_context["type"] == "breakout" and pending_context.get(
                "retest_zone"
            ):
                rz_low, rz_high = pending_context["retest_zone"]
                if not (rz_low <= current_price <= rz_high):
                    # We only allow trade if we are inside the retest zone
                    funnel["blocked_retest_zone"] += 1
                    continue

            if not is_tradable:
                continue

            if direction == pending_context["direction"]:
                # print(f"DEBUG Aggression: dir={direction}, p_dir={pending_context['direction']}, first_seen={first_impulse_seen}")
                funnel.setdefault("passed_lvn", 0)
                funnel["passed_lvn"] += 1

                # STEP 4: First Impulse Ignored
                if not first_impulse_seen:
                    funnel["blocked_aggression_impulse"] += 1
                    first_impulse_seen = True
                    continue  # Wait for retest (second impulse)
                funnel["passed_aggression"] += 1

                # 2. Internal POC Confirmation
                try:
                    # Combine ticks and time for accurate aggression window
                    aggression_time = row["ts"]
                    max_seconds = pd.Timedelta(seconds=30)

                    tick_window = events_df.iloc[max(0, i - 60) : i + 1]
                    time_window = tick_window[
                        tick_window["ts"] >= (aggression_time - max_seconds)
                    ]

                    # Take the smaller window
                    mini_df = time_window if len(time_window) > 0 else tick_window
                    internal_poc = mini_df.groupby("price")["size"].sum().idxmax()

                    # Institutional Filter 7: Internal POC (RELAXED)
                    # We allow entry if price is within a small tolerance of POC
                    # instead of requiring a strict close beyond it.
                    tick_size = 0.25
                    poc_tolerance = tick_size * 4 # 1.0 point tolerance for NQ
                    
                    is_strict_pass = (direction == "sell" and current_price < internal_poc) or \
                                     (direction == "buy" and current_price > internal_poc)
                    
                    is_relaxed_pass = (direction == "sell" and current_price < (internal_poc + poc_tolerance)) or \
                                      (direction == "buy" and current_price > (internal_poc - poc_tolerance))

                    if is_strict_pass:
                        funnel["internal_poc_strict_pass"] += 1

                    if not is_relaxed_pass:
                        funnel["blocked_internal_poc"] += 1
                        continue
                    
                    if is_relaxed_pass and not is_strict_pass:
                        funnel["relaxed_poc_saves"] += 1
                        
                    funnel["passed_internal_poc"] += 1
                except Exception as e:
                    pass

                # STEP 4: Aggression Confirmed! ENTRY!
                event_type = f"confirmed_{pending_context['type']}"
                pending_context = None
            else:
                continue  # Still waiting for matching big_trade
        else:
            continue

        # STEP 3: Confluence Scoring
        score = 0
        if direction == bias.lower():
            score += 1  # Volume confirms direction
        if row.get("cvd_divergence"):
            score += 1
        if row.get("deep_effort"):
            score += 1
        if "confirmed" in event_type:
            score += 2  # Absorption/Trap + Aggression = highly valid

        # Validate Edge
        size_mult = 1.0
        if score < 2:
            funnel["blocked_score_threshold"] += 1
            continue
        
        funnel["passed_score"] += 1

        if direction != bias.lower():
            funnel["blocked_direction_mismatch"] += 1
            continue

        if use_validated_edge:
            allowed, stability = edge_validator.is_trade_allowed(
                row, current_regime=regime_type
            )
            # print(f"DEBUG edge: regime={regime_type}, allowed={allowed}, stability={stability:.3f}, atr={row.get('atr', 10):.1f}")
            if not allowed:
                funnel["blocked_edge_validator"] += 1
                continue
            
        funnel["passed_edge"] += 1

        # STEP 5: Scaling with profit
        if daily_pnl <= 0:
            size_mult = 1.0  # 0.25% base risk
        elif score >= 4:
            size_mult = min(daily_pnl * 0.5, 4.0)  # Scale aggressively
        elif score >= 3:
            size_mult = 2.0  # 0.50%

        vol = row.get("volatility", 10)
        tick_size = 0.25  # NQ tick size
        risk = max(20, vol * 0.5)
        MIN_STOP_PTS = 20.0

        # print(f"DEBUG entry: direction={direction}, price={current_price}, vol={row.get('volatility', 'MISSING')}, risk={risk}")
        if direction == "buy":
            stop = current_price - risk + tick_size
            # Применяем минимальный стоп
            if (current_price - stop) < MIN_STOP_PTS:
                stop = current_price - MIN_STOP_PTS
            
            target = (
                poc
                if poc and poc > current_price + (current_price - stop)
                else current_price + (current_price - stop) * 2.0
            )
        else:
            stop = current_price + risk - tick_size
            # Применяем минимальный стоп
            if (stop - current_price) < MIN_STOP_PTS:
                stop = current_price + MIN_STOP_PTS

            target = (
                poc
                if poc and poc < current_price - (stop - current_price)
                else current_price - (stop - current_price) * 2.0
            )

        # MINIMUM R:R CHECK
        calc_risk = abs(current_price - stop)
        calc_reward = abs(target - current_price)
        # print(f"DEBUG rr: calc_risk={calc_risk:.2f}, calc_reward={calc_reward:.2f}, ratio={calc_reward/(calc_risk+1e-9):.2f}")
        if calc_risk == 0 or (calc_reward / calc_risk) < 1.5:
            # R:R is too poor, skip entry
            funnel["blocked_rr_too_low"] += 1
            continue

        # Institutional Trade Cooldown (RECALIBRATED)
        if last_trade_time:
            time_since_last = (row["ts"] - last_trade_time)
            last_trade_dir = trades[-1]["direction"] if trades else None
            
            is_strict_cooldown = time_since_last < pd.Timedelta(minutes=30)
            
            # Relaxed rules:
            # 1. Reduce window to 5 mins
            # 2. Allow re-entry if high conviction (score >= 4)
            # 3. Allow re-entry if opposite direction (market flip) after 2 mins
            
            relaxed_window = pd.Timedelta(minutes=5)
            high_conviction = score >= 4
            direction_flip = direction != last_trade_dir
            
            is_relaxed_cooldown = time_since_last < relaxed_window
            
            if is_strict_cooldown:
                funnel["cooldown_strict_rejections"] += 1
                
                # Bypasses:
                if high_conviction:
                    funnel["cooldown_bypass_high_score"] += 1
                    is_relaxed_cooldown = False
                elif direction_flip and time_since_last > pd.Timedelta(minutes=2):
                    funnel["cooldown_relaxed_saves"] += 1
                    is_relaxed_cooldown = False
                elif not is_relaxed_cooldown:
                    funnel["cooldown_relaxed_saves"] += 1

            if is_relaxed_cooldown:
                funnel["blocked_trade_cooldown"] += 1
                continue

        trades.append(
            {
                "ts": row["ts"],
                "symbol": row.get("symbol", "NQ"),
                "direction": direction,
                "entry_price": current_price,
                "stop": stop,
                "original_stop": stop,
                "entry_cvd": row.get("cvd", 0),
                "target": target,
                "size_mult": round(size_mult, 2),
                "regime": regime_type,
                "event_type": event_type,
                "location": row.get("location", "MID"),
                "session": row.get("session", "Asia"),
                "trend": row.get("trend", "range"),
                "sequence": row.get("sequence_pattern", "none"),
                "score": score,
                "delta": row.get("delta", 0),
                "imbalance": row.get("orderbook_imbalance", 0),
                "volatility": vol,
                "exit_price": None,
                "outcome_R": 0,
                "r_multiple": 0,
                "result": "open",
                "features": {k: v for k, v in row.items()},
            }
        )
        in_position = True
        last_trade_time = row["ts"]
        traded_levels.add(current_price)

    # Force close open trades at EOD
    if not events_df.empty:
        last_price = events_df.iloc[-1]["price"]
        for trade in trades:
            if trade["result"] == "open":
                trade["exit_price"] = last_price
                pnl = (last_price - trade["entry_price"]) * (
                    1 if trade["direction"] == "buy" else -1
                )
                trade["result"] = "win" if pnl > 0 else "loss"
                trade["r_multiple"] = pnl / abs(trade["entry_price"] - trade["original_stop"])
                trade["outcome_R"] = trade["r_multiple"] * trade["size_mult"]
                trade["pnl"] = pnl
                trade["pnl_pts"] = pnl
                trade["exit_reason"] = "closed_eod"

    finished_trades = [t for t in trades if t["result"] in ("win", "loss")]
    for t in finished_trades:
        t["is_win"] = t["result"] == "win"

    wins = sum(1 for t in finished_trades if t["is_win"])
    total = len(finished_trades)

    print(
        f"📊 L3 Backtest Results: {total} trades executed from {len(events_df)} analyzed events."
    )
    
    # --- FULL FUNNEL DIAGNOSTICS TABLE ---
    print("\n" + "="*50)
    print("📈 FINAL TRADE GENERATION FUNNEL")
    print("="*50)
    
    stages = [
        ("Total Analyzed Events", funnel.get("total_events", 0)),
        ("Passed Boundary (VAH/VAL)", funnel.get("passed_boundary", 0)),
        ("Passed Bias Match", funnel.get("passed_bias_match", 0)),
        ("Passed Aggression", funnel.get("passed_aggression", 0)),
        ("Passed Internal POC", funnel.get("passed_internal_poc", 0)),
        ("Passed Score Threshold", funnel.get("passed_score", 0)),
        ("Passed Edge Validator", funnel.get("passed_edge", 0)),
        ("Final Executed Trades", total)
    ]
    
    for stage, count in stages:
        print(f"{stage:<30} : {count:>8}")
    
    print("-" * 50)
    
    rejections = {
        "Session Time": funnel.get("blocked_session_time", 0),
        "Unclear State": funnel.get("blocked_unclear", 0),
        "Bias Cooldown": funnel.get("blocked_bias_cooldown", 0),
        "Boundary Gap": funnel.get("blocked_boundary", 0),
        "Bias Mismatch": funnel.get("blocked_bias_match", 0),
        "Structural Invalid": funnel.get("blocked_structural_invalidation", 0),
        "Retest Zone": funnel.get("blocked_retest_zone", 0),
        "First Impulse Only": funnel.get("blocked_aggression_impulse", 0),
        "Internal POC": funnel.get("blocked_internal_poc", 0),
        "Low Score": funnel.get("blocked_score_threshold", 0),
        "Direction Mismatch": funnel.get("blocked_direction_mismatch", 0),
        "Edge Validator": funnel.get("blocked_edge_validator", 0),
        "Poor RR": funnel.get("blocked_rr_too_low", 0),
        "Trade Cooldown": funnel.get("blocked_trade_cooldown", 0),
    }
    
    # Sort rejections by frequency
    sorted_rejections = sorted(rejections.items(), key=lambda x: x[1], reverse=True)
    
    print("❌ TOP 5 REJECTION CAUSES:")
    for i, (reason, count) in enumerate(sorted_rejections[:5]):
        print(f"{i+1}. {reason:<25} : {count:>8} rejections")
    print("="*50 + "\n")

    # Debug Internal POC relaxation
    s_pass = funnel.get("internal_poc_strict_pass", 0)
    r_pass = funnel.get("passed_internal_poc", 0)
    increase = ((r_pass - s_pass) / max(1, s_pass)) * 100
    print(f"[DEBUG] Filter 7 (Internal POC) Relaxation:")
    print(f"  - Previous pass count (strict): {s_pass}")
    print(f"  - New pass count (relaxed):    {r_pass}")
    # Debug Cooldown relaxation
    s_rej = funnel.get("cooldown_strict_rejections", 0)
    bypassed = funnel.get("cooldown_bypass_high_score", 0) + funnel.get("cooldown_relaxed_saves", 0)
    print(f"[DEBUG] Trade Cooldown Recalibration:")
    print(f"  - Strict rejections avoided:  {bypassed} / {max(1, s_rej)}")
    print(f"  - High-score bypasses:        {funnel.get('cooldown_bypass_high_score', 0)}")
    print(f"  - Relaxed window/Flip saves:  {funnel.get('cooldown_relaxed_saves', 0)}")
    print("-" * 50)

    stats = {
        "total_trades": total,
        "win_rate": (wins / total * 100) if total > 0 else 0,
        "avg_R": np.mean([t["outcome_R"] for t in finished_trades])
        if finished_trades
        else 0,
        "total_R": sum(t["outcome_R"] for t in finished_trades)
        if finished_trades
        else 0,
        "regime": regime_type,
        "events_analyzed": len(events_df),
        "daily_loss_limit_hit": daily_loss_limit_hit,
    }

    return {
        "trades": finished_trades, 
        "stats": stats, 
        "funnel": funnel,
        "poc": poc,
        "vah": vah,
        "val": val,
        "bias": bias,
    }


def save_trades_to_history(trades: list):
    """Saves trades to data/processed/trades.parquet for analysis."""
    if not trades:
        return
    os.makedirs("data/processed", exist_ok=True)
    path = "data/processed/trades.parquet"
    new_df = pd.DataFrame(trades)
    if os.path.exists(path):
        old_df = pd.read_parquet(path)
        combined = pd.concat([old_df, new_df], ignore_index=True)
        combined.drop_duplicates(subset=["ts", "symbol", "entry_price"], inplace=True)
        combined.to_parquet(path)
    else:
        new_df.to_parquet(path)
    print(f"📁 Logged {len(trades)} trades to {path}")

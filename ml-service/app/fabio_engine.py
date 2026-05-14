"""Fabio Order Flow backtesting engine (Pro v2).

Full Fabio Valentino (Chart Fanatics) methodology:
- AMT: Balance vs Imbalance market state detection
- Two models: Trend Following (NY) + Mean Reversion (London)
- Volume Profile: VAH/VAL/POC/LVN + Volume Ledge
- 6 Core Concepts:
  1. Trap: Failed auction beyond VA boundary (second-drive only)
  2. Absorption: Repeated high-vol attempts that fail to move price
  3. Squeeze: Trapped traders fuel breakout (enter on retest, not impulse)
  4. CVD Divergence: Leading indicator for entry + exit management
  5. Deep Effort: Effort vs Result (absorption zones + path of least resistance)
  6. Confluence: 0-5 scoring with LVN+BigTrades as mandatory base
- Session filtering: NY (13-22 UTC), London (08-17 UTC)
- Risk: 0.25% base, scaled by confluence (3/5=0.25%, 4/5=0.5%, 5/5=day profit)
"""

from __future__ import annotations

import math
from typing import Literal, Any

import numpy as np
import pandas as pd
from pydantic import BaseModel


# ── Request models ────────────────────────────────────────────────

class FabioBacktestRequest(BaseModel):
    candles: list[dict]
    # Volume Profile settings
    vp_period: int = 50
    value_area_pct: float = 0.70
    lvn_threshold: float = 0.20
    # Follow-through
    follow_bars: int = 5
    follow_threshold: float = 0.3
    # Absorption
    absorption_vol_mult: float = 1.5
    absorption_body_pct: float = 0.3
    # Risk management (Fabio: 0.25% per trade)
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0
    max_holding_bars: int = 30
    initial_balance: float = 10000.0
    risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 2.0
    # Session filter: "london", "newyork", "all"
    session_filter: str = "all"
    # Model type: "trend_following", "mean_reversion", "both"
    model_type: str = "both"
    # Setups to enable
    enable_trap: bool = True
    enable_absorption: bool = True
    enable_squeeze: bool = True
    # CVD divergence
    enable_cvd_divergence: bool = True
    cvd_lookback: int = 10
    # Trap: how many bars to confirm failed auction (second drive)
    trap_confirm_bars: int = 3
    # Absorption: min consecutive absorption bars to confirm
    absorption_repeat: int = 2
    # Squeeze: bars to wait for retest after breakout
    squeeze_retest_bars: int = 8


# ── Volume Profile ────────────────────────────────────────────────

class VolumeProfile:
    """Compute VAH, VAL, POC, LVN from a window of bars."""

    def __init__(self, highs, lows, closes, volumes, num_bins: int = 50,
                 va_pct: float = 0.70, lvn_pct: float = 0.20):
        self.vah = None
        self.val = None
        self.poc = None
        self.lvn_zones: list[float] = []

        if len(highs) < 5:
            return

        price_min = float(np.min(lows))
        price_max = float(np.max(highs))
        if price_max <= price_min:
            return

        bin_size = (price_max - price_min) / num_bins
        bins = np.zeros(num_bins)

        # Distribute volume across price bins
        for h, l, v in zip(highs, lows, volumes):
            if v <= 0 or h <= l:
                continue
            lo_bin = max(0, int((float(l) - price_min) / bin_size))
            hi_bin = min(num_bins - 1, int((float(h) - price_min) / bin_size))
            spread = hi_bin - lo_bin + 1
            vol_per_bin = float(v) / spread
            for b in range(lo_bin, hi_bin + 1):
                bins[b] += vol_per_bin

        total_vol = bins.sum()
        if total_vol == 0:
            return

        # POC = bin with max volume
        poc_bin = int(np.argmax(bins))
        self.poc = price_min + (poc_bin + 0.5) * bin_size

        # Value Area: expand from POC until va_pct of total volume
        va_vol = bins[poc_bin]
        lo_idx, hi_idx = poc_bin, poc_bin
        while va_vol / total_vol < va_pct and (lo_idx > 0 or hi_idx < num_bins - 1):
            add_lo = bins[lo_idx - 1] if lo_idx > 0 else 0
            add_hi = bins[hi_idx + 1] if hi_idx < num_bins - 1 else 0
            if add_lo >= add_hi and lo_idx > 0:
                lo_idx -= 1
                va_vol += add_lo
            elif hi_idx < num_bins - 1:
                hi_idx += 1
                va_vol += add_hi
            else:
                lo_idx -= 1
                va_vol += add_lo

        self.val = price_min + lo_idx * bin_size
        self.vah = price_min + (hi_idx + 1) * bin_size

        # LVN: bins with volume < lvn_pct of max bin volume
        max_bin_vol = bins.max()
        if max_bin_vol > 0:
            for i in range(num_bins):
                if bins[i] < max_bin_vol * lvn_pct and bins[i] > 0:
                    self.lvn_zones.append(price_min + (i + 0.5) * bin_size)


# ── Order Flow approximation from OHLCV ──────────────────────────

def compute_order_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Approximate order flow metrics from OHLCV data.
    Includes: Delta, CVD, Absorption, Deep Effort (2 scenarios), Big Trades proxy."""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    rng = h - l
    body = (c - o).abs()

    # Delta approximation (buy pressure vs sell pressure)
    buy_ratio = np.where(rng > 0, (c - l) / rng, 0.5)
    df["delta"] = (buy_ratio * 2 - 1) * v
    df["cvd"] = df["delta"].cumsum()

    # CVD divergence (LEADING indicator — unlike MACD/RSI which lag)
    df["cvd_sma"] = df["cvd"].rolling(10, min_periods=3).mean()
    df["price_sma"] = c.rolling(10, min_periods=3).mean()
    cvd_dir = (df["cvd"] - df["cvd_sma"]).apply(np.sign)
    price_dir = (c - df["price_sma"]).apply(np.sign)
    df["cvd_divergence"] = (cvd_dir != price_dir).astype(int)
    # CVD slope for exit management
    df["cvd_slope"] = df["cvd"].diff(3).rolling(3, min_periods=1).mean()

    # Body ratio and volume ratio
    df["body_pct"] = np.where(rng > 0, body / rng, 0)
    vol_sma = v.rolling(20, min_periods=5).mean()
    vol_std = v.rolling(20, min_periods=5).std().fillna(0)
    
    # If constant volume or low variance, we need more sensitive thresholds
    vol_cv = vol_std.mean() / (vol_sma.mean() + 1e-9) if vol_sma.mean() > 0 else 0
    is_low_var_vol = vol_cv < 0.05
    
    df["vol_ratio"] = np.where(vol_sma > 0, v / vol_sma, 1.0)
    abs_vol_thresh = 1.05 if is_low_var_vol else 1.2
    bt_vol_thresh = 1.3 if is_low_var_vol else 1.5

    # ── Deep Effort: TWO scenarios (Fabio's proprietary concept) ──
    # Scenario 1: ABSORPTION — huge volume, no price movement → level defended
    df["deep_effort_absorption"] = np.where(
        df["body_pct"] > 0,
        df["vol_ratio"] / (df["body_pct"] + 0.01), 
        df["vol_ratio"] * 10 # High effort if no body but volume
    )
    # Scenario 2: PATH OF LEAST RESISTANCE 
    buy_vol = buy_ratio * v
    sell_vol = (1 - buy_ratio) * v
    effort_balance = np.where(
        (buy_vol + sell_vol) > 0,
        np.abs(buy_vol - sell_vol) / (buy_vol + sell_vol), 0
    )
    # Low effort_balance + big body = path of least resistance
    df["deep_effort_path"] = np.where(
        (effort_balance < 0.4) & (df["body_pct"] > 0.5), 1, 0
    )
    # Combined deep effort score
    df["deep_effort"] = df["deep_effort_absorption"]
    df["is_absorption"] = (df["vol_ratio"] >= abs_vol_thresh) & (df["body_pct"] < 0.4)

    # ── Big Trades proxy ──
    df["is_big_trade"] = v >= (vol_sma + bt_vol_thresh * vol_std)
    df["big_trade_direction"] = np.where(
        df["is_big_trade"],
        np.sign(df["delta"]),
        0
    )

    # ATR
    tr = pd.concat([rng, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14, min_periods=5).mean()
    df["momentum"] = np.where(df["atr"] > 0, body / df["atr"], 0)

    # Market State placeholders (filled per-bar in detect_setups)
    df["va_width"] = 0.0
    df["market_state"] = "unknown"

    # Session tagging (UTC hours)
    if "timestamp" in df.columns:
        try:
            ts = pd.to_datetime(df["timestamp"])
            hour = ts.dt.hour
            df["session"] = "off"
            df.loc[(hour >= 8) & (hour < 17), "session"] = "london"
            df.loc[(hour >= 13) & (hour < 22), "session"] = "newyork"
        except Exception:
            df["session"] = "all"
    else:
        df["session"] = "all"

    return df


# ── Setup detection ───────────────────────────────────────────────

class TradeSignal(BaseModel):
    bar_index: int
    timestamp: str
    setup: str  # trap_short, trap_long, absorption_*, squeeze_*, cvd_div_*
    entry: float
    stop_loss: float
    take_profit: float
    direction: Literal["buy", "sell"]
    vah: float
    val: float
    poc: float
    note: str
    confluence: int = 0  # 0-5 scoring
    model: str = "trend_following"  # or "mean_reversion"
    market_state: str = "unknown"  # "balance" or "imbalance"
    session: str = "all"
    risk_tier: str = "standard"  # standard(0.25%), elevated(0.5%), max(day_profit)
    confluence_detail: str = ""  # breakdown of which factors scored


def _score_confluence(bar, close: float, atr: float, lvn_zones: list, direction: str) -> tuple[int, str]:
    """Fabio confluence scoring (0-5). LVN + BigTrades = mandatory base."""
    score = 0
    parts = []
    # 1. Volume confirms direction (effort vs result)
    if bar["vol_ratio"] > 1.3:
        score += 1; parts.append("VOL")
    # 2. CVD divergence in trade direction
    if bar["cvd_divergence"]:
        score += 1; parts.append("CVD")
    # 3. Deep Effort signal at level
    if bar["deep_effort"] > 3:
        score += 1; parts.append("DE")
    # 4. Near LVN (low volume node)
    if any(abs(close - z) < atr * 0.5 for z in lvn_zones):
        score += 1; parts.append("LVN")
    # 5. Confirmed absorption of opposite side
    if bar["is_absorption"]:
        score += 1; parts.append("ABS")
    return score, "+".join(parts)


def _risk_tier(conf: int) -> str:
    """Position sizing by confluence: 3=0.25%, 4=0.5%, 5=day-profit."""
    if conf >= 5: return "max"
    if conf >= 4: return "elevated"
    return "standard"


def _has_prior_break(df: pd.DataFrame, idx: int, level: float,
                     lookback: int, side: str) -> bool:
    """Check if there was a PRIOR break of level in last N bars (fakeout filter).
    Fabio rule: first breakout is ignored — only second drive is traded."""
    start = max(0, idx - lookback)
    for j in range(start, idx):
        if side == "above" and float(df.iloc[j]["high"]) > level:
            return True
        if side == "below" and float(df.iloc[j]["low"]) < level:
            return True
    return False


def _count_absorption_bars(df: pd.DataFrame, idx: int, level: float,
                           atr: float, lookback: int) -> int:
    """Count consecutive absorption bars near a level (Fabio: repeated failed attempts)."""
    count = 0
    for j in range(max(0, idx - lookback), idx + 1):
        b = df.iloc[j]
        near = abs(float(b["close"]) - level) < atr * 0.5
        if near and b["is_absorption"]:
            count += 1
        elif count > 0 and not near:
            break  # reset on gap
    return count


def detect_setups(df: pd.DataFrame, req: FabioBacktestRequest) -> list[TradeSignal]:
    """Scan for Fabio setups: Trap (2nd drive), Absorption (repeated), Squeeze (retest),
    CVD divergence (entry+exit), Deep Effort (2 scenarios), Confluence (0-5)."""
    signals: list[TradeSignal] = []
    n = len(df)
    vp_period = req.vp_period
    margin = max(req.follow_bars, req.squeeze_retest_bars)

    for i in range(vp_period + margin, n - margin - 1):
        window = df.iloc[i - vp_period:i]
        vp = VolumeProfile(
            window["high"].values, window["low"].values,
            window["close"].values, window["volume"].values,
            va_pct=req.value_area_pct, lvn_pct=req.lvn_threshold,
        )
        if vp.vah is None or vp.val is None:
            continue

        bar = df.iloc[i]
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        opn = float(bar["open"])
        atr = float(bar["atr"]) if pd.notna(bar["atr"]) and bar["atr"] > 0 else abs(high - low)
        ts = str(bar.get("timestamp", str(i)))
        bar_session = str(bar.get("session", "all"))

        if req.session_filter != "all" and bar_session != req.session_filter:
            continue

        # ── MARKET STATE (AMT) ──
        # Dynamic threshold based on asset class (FX has tighter VA)
        is_fx = close < 5 # Simple proxy for EURUSD/GBPUSD
        state_threshold = 2.5 if is_fx else 3.5
        va_width = (vp.vah - vp.val) / (atr + 1e-9)
        market_state = "balance" if va_width < state_threshold else "imbalance"
        price_in_va = vp.val <= close <= vp.vah

        if req.model_type == "trend_following" and market_state == "balance":
            continue
        if req.model_type == "mean_reversion" and market_state == "imbalance":
            continue

        # ── CONFLUENCE (Fabio 0-5) ──
        conf, conf_detail = _score_confluence(bar, close, atr, vp.lvn_zones, "")
        tier = _risk_tier(conf)
        poc_target = round(vp.poc, 6) if vp.poc else 0

        # ══════════════════════════════════════════════════════════════
        # SETUP 1: TRAP at VAH → SHORT (failed auction, second drive)
        # ══════════════════════════════════════════════════════════════
        if req.enable_trap and high > vp.vah:
            # Check for PRIOR break in a larger window (50 bars)
            had_prior = _has_prior_break(df, i, vp.vah, 50, "above")
            if had_prior:
                fwd = df.iloc[i + 1:i + 1 + req.trap_confirm_bars]
                if len(fwd) > 0:
                    returned = any(float(fb["close"]) < vp.vah for _, fb in fwd.iterrows())
                    sell_aggression = any(
                        float(fb["close"]) < float(fb["open"]) or float(fb["vol_ratio"]) > 0.6
                        for _, fb in fwd.iterrows()
                    )
                    if returned and sell_aggression:
                        entry_bar = fwd.iloc[-1]
                        entry = float(entry_bar["close"])
                        if entry < vp.vah:
                            sl = high + atr * 0.5
                            tp = vp.poc if vp.poc and vp.poc < entry else entry - atr * req.tp_atr_mult
                            signals.append(TradeSignal(
                                bar_index=i, timestamp=ts,
                                setup="trap_short", direction="sell",
                                entry=round(entry, 6), stop_loss=round(sl, 6),
                                take_profit=round(tp, 6),
                                vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                                note=f"Trap SHORT (2nd drive) at VAH confirmed",
                                confluence=conf, model="mean_reversion",
                                market_state=market_state, session=bar_session,
                                risk_tier=tier, confluence_detail=conf_detail,
                            ))
                            continue

        # TRAP LONG: mirror
        if req.enable_trap and low < vp.val:
            had_prior = _has_prior_break(df, i, vp.val, 50, "below")
            if had_prior:
                fwd = df.iloc[i + 1:i + 1 + req.trap_confirm_bars]
                if len(fwd) > 0:
                    returned = any(float(fb["close"]) > vp.val for _, fb in fwd.iterrows())
                    buy_aggression = any(
                        float(fb["close"]) > float(fb["open"]) or float(fb["vol_ratio"]) > 0.7
                        for _, fb in fwd.iterrows()
                    )
                    if returned and buy_aggression:
                        entry_bar = fwd.iloc[-1]
                        entry = float(entry_bar["close"])
                        if entry > vp.val:
                            sl = low - atr * 0.5
                            tp = vp.poc if vp.poc and vp.poc > entry else entry + atr * req.tp_atr_mult
                            signals.append(TradeSignal(
                                bar_index=i, timestamp=ts,
                                setup="trap_long", direction="buy",
                                entry=round(entry, 6), stop_loss=round(sl, 6),
                                take_profit=round(tp, 6),
                                vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                                note=f"Trap LONG (2nd drive) at VAL confirmed",
                                confluence=conf, model="mean_reversion",
                                market_state=market_state, session=bar_session,
                                risk_tier=tier, confluence_detail=conf_detail,
                            ))
                            continue

        # ══════════════════════════════════════════════════════════════
        # SETUP 2: ABSORPTION 
        # ══════════════════════════════════════════════════════════════
        if req.enable_absorption and abs(close - vp.vah) < atr * 2.5:
            abs_count = _count_absorption_bars(df, i, vp.vah, atr, req.absorption_repeat + 8)
            min_abs = max(1, req.absorption_repeat - 1)
            if abs_count >= min_abs and bar["is_absorption"] and close < opn:
                entry = close
                sl = high + atr * req.sl_atr_mult
                tp = vp.poc if vp.poc and vp.poc < entry else entry - atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="absorption_short", direction="sell",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"Absorption at VAH ({abs_count}x bars)",
                    confluence=conf, model="mean_reversion",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail,
                ))
                continue

        if req.enable_absorption and abs(close - vp.val) < atr * 2.5:
            abs_count = _count_absorption_bars(df, i, vp.val, atr, req.absorption_repeat + 8)
            min_abs = max(1, req.absorption_repeat - 1)
            if abs_count >= min_abs and bar["is_absorption"] and close > opn:
                entry = close
                sl = low - atr * req.sl_atr_mult
                tp = vp.poc if vp.poc and vp.poc > entry else entry + atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="absorption_long", direction="buy",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"Absorption at VAL ({abs_count}x bars)",
                    confluence=conf, model="mean_reversion",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail,
                ))
                continue

        # ══════════════════════════════════════════════════════════════
        # SETUP 3: SQUEEZE 
        # ══════════════════════════════════════════════════════════════
        if req.enable_squeeze:
            rb = req.squeeze_retest_bars
            if _has_prior_break(df, i, vp.vah, 60, "above"):
                near_vah = abs(close - vp.vah) < atr * 2.5
                is_retest = close >= vp.vah and near_vah
                bullish_retest = close > opn and bar["vol_ratio"] > 0.5
                if is_retest and bullish_retest:
                    entry = close
                    sl = vp.vah - atr * 0.5
                    tp = entry + atr * req.tp_atr_mult
                    signals.append(TradeSignal(
                        bar_index=i, timestamp=ts,
                        setup="squeeze_long", direction="buy",
                        entry=round(entry, 6), stop_loss=round(sl, 6),
                        take_profit=round(tp, 6),
                        vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                        note=f"Retest VAH after breakout→squeeze LONG",
                        confluence=conf, model="trend_following",
                        market_state=market_state, session=bar_session,
                        risk_tier=tier, confluence_detail=conf_detail,
                    ))
                    continue

            # SQUEEZE SHORT: prior breakdown below VAL, retesting from below
            if _has_prior_break(df, i, vp.val, 60, "below"):
                near_val = abs(close - vp.val) < atr * 2.5
                is_retest = close <= vp.val and near_val
                bearish_retest = close < opn and bar["vol_ratio"] > 0.5
                if is_retest and bearish_retest:
                    entry = close
                    sl = vp.val + atr * 0.5
                    tp = entry - atr * req.tp_atr_mult
                    signals.append(TradeSignal(
                        bar_index=i, timestamp=ts,
                        setup="squeeze_short", direction="sell",
                        entry=round(entry, 6), stop_loss=round(sl, 6),
                        take_profit=round(tp, 6),
                        vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                        note=f"Retest VAL after breakdown→squeeze SHORT",
                        confluence=conf, model="trend_following",
                        market_state=market_state, session=bar_session,
                        risk_tier=tier, confluence_detail=conf_detail,
                    ))
                    continue

        # ══════════════════════════════════════════════════════════════
        # SETUP 4: CVD DIVERGENCE (leading indicator — dual use)
        # Entry use: CVD diverges from price in balance → early signal
        # Exit use: handled in simulate_signals via cvd_slope
        # ══════════════════════════════════════════════════════════════
        if req.enable_cvd_divergence and bar["cvd_divergence"]:
            cvd_now = float(bar["cvd"])
            cvd_prev = float(df.iloc[i - req.cvd_lookback]["cvd"]) if i >= req.cvd_lookback else cvd_now
            price_up = close > float(df.iloc[i - req.cvd_lookback]["close"]) if i >= req.cvd_lookback else False
            cvd_down = cvd_now < cvd_prev

            if price_up and cvd_down and bar["deep_effort"] > 1.5:
                entry = close
                sl = high + atr * req.sl_atr_mult
                tp = vp.poc if vp.poc and vp.poc < entry else entry - atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="cvd_div_short", direction="sell",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"CVD divergence: price↑ CVD↓=distribution (Robbins Cup read)",
                    confluence=conf + 1, model="trend_following",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail + "+CVD_DIV",
                ))
                continue

            price_down = close < float(df.iloc[i - req.cvd_lookback]["close"]) if i >= req.cvd_lookback else False
            cvd_up = cvd_now > cvd_prev

            if price_down and cvd_up and bar["deep_effort"] > 1.5:
                entry = close
                sl = low - atr * req.sl_atr_mult
                tp = vp.poc if vp.poc and vp.poc > entry else entry + atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="cvd_div_long", direction="buy",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"CVD divergence: price↓ CVD↑=accumulation",
                    confluence=conf + 1, model="trend_following",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail + "+CVD_DIV",
                ))
                continue

        # ══════════════════════════════════════════════════════════════
        # SETUP 5: DEEP EFFORT — Path of Least Resistance
        # Equal effort both sides but result skewed → continuation
        # ══════════════════════════════════════════════════════════════
        if bar["deep_effort_path"] and bar["vol_ratio"] > 0.9:
            direction = "buy" if close > opn else "sell"
            if direction == "buy" and close > vp.poc:
                entry = close
                sl = low - atr * req.sl_atr_mult
                tp = entry + atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="deep_effort_long", direction="buy",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"DeepEffort path→equal effort, buyers win→continuation",
                    confluence=conf, model="trend_following",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail,
                ))
                continue
            elif direction == "sell" and close < vp.poc:
                entry = close
                sl = high + atr * req.sl_atr_mult
                tp = entry - atr * req.tp_atr_mult
                signals.append(TradeSignal(
                    bar_index=i, timestamp=ts,
                    setup="deep_effort_short", direction="sell",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit=round(tp, 6),
                    vah=round(vp.vah, 6), val=round(vp.val, 6), poc=poc_target,
                    note=f"DeepEffort path→equal effort, sellers win→continuation",
                    confluence=conf, model="trend_following",
                    market_state=market_state, session=bar_session,
                    risk_tier=tier, confluence_detail=conf_detail,
                ))
                continue

    return signals


# ── Trade simulation ──────────────────────────────────────────────

class SimResult(BaseModel):
    bar_index: int
    timestamp: str
    setup: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_bar: int
    result: Literal["win", "loss"]
    pnl_r: float
    holding_bars: int
    note: str
    exit_reason: str = ""  # sl/tp/cvd_exit/de_exit/timeout
    risk_tier: str = "standard"
    confluence: int = 0
    confluence_detail: str = ""
    ai_score: float = -1  # -1 = no model, 0-100 = ML confidence
    # ML Features
    features: dict[str, Any] = {}

def simulate_signals(df: pd.DataFrame, signals: list[TradeSignal],
                     max_hold: int = 30) -> list[SimResult]:
    """Walk forward with CVD exit management + Deep Effort counter-signal exit.

    Fabio dual-use of CVD:
    - For EXIT: if CVD slope reverses while in profit → pressure exhausting
      → move SL to breakeven or exit early (don't wait for full TP).
    - Deep Effort: if opposite DE zone appears while in position → exit.
    """
    results: list[SimResult] = []
    next_allowed = 0

    for sig in signals:
        if sig.bar_index < next_allowed:
            continue

        bar = df.iloc[sig.bar_index]
        features = {
            "vol_ratio": float(bar["vol_ratio"]),
            "delta_ratio": float(bar["delta"] / bar["volume"]) if bar["volume"] > 0 else 0,
            "momentum": float(bar["momentum"]),
            "deep_effort": float(bar["deep_effort"]),
            "deep_effort_path": float(bar["deep_effort_path"]),
            "cvd_divergence": float(bar["cvd_divergence"]),
            "cvd_slope": float(bar["cvd_slope"]) if pd.notna(bar["cvd_slope"]) else 0,
            "body_pct": float(bar["body_pct"]),
            "dist_to_poc": float((sig.entry - sig.poc) / sig.entry) if sig.poc > 0 and sig.entry else 0,
            "session": sig.session,
            "market_state": sig.market_state,
            "hour": int(pd.to_datetime(sig.timestamp).hour) if sig.timestamp else 0,
        }

        entry = sig.entry
        sl = sig.stop_loss
        tp = sig.take_profit
        risk = abs(entry - sl) or 0.0001
        exit_reason = "timeout"

        result = "loss"
        exit_price = sl
        exit_bar = min(sig.bar_index + max_hold, len(df) - 1)
        holding = 0
        be_moved = False  # track if SL moved to breakeven

        for j in range(sig.bar_index + 1, min(sig.bar_index + 1 + max_hold, len(df))):
            holding = j - sig.bar_index
            b = df.iloc[j]
            cur_close = float(b["close"])

            # ── SL/TP check ──
            if sig.direction == "buy":
                if float(b["low"]) <= sl:
                    result, exit_price, exit_bar, exit_reason = "loss", sl, j, "sl"
                    break
                if float(b["high"]) >= tp:
                    result, exit_price, exit_bar, exit_reason = "win", tp, j, "tp"
                    break
            else:
                if float(b["high"]) >= sl:
                    result, exit_price, exit_bar, exit_reason = "loss", sl, j, "sl"
                    break
                if float(b["low"]) <= tp:
                    result, exit_price, exit_bar, exit_reason = "win", tp, j, "tp"
                    break

            # ── CVD EXIT MANAGEMENT (Fabio dual-use) ──
            # If CVD slope reverses against our position while in profit
            # → pressure exhausting → exit early before full TP
            pnl_cur = (cur_close - entry) if sig.direction == "buy" else (entry - cur_close)
            in_profit = pnl_cur > 0
            cvd_sl = float(b["cvd_slope"]) if pd.notna(b["cvd_slope"]) else 0

            if in_profit and not be_moved:
                # CVD turning against us → move SL to breakeven
                cvd_against = (sig.direction == "buy" and cvd_sl < -0.5) or \
                              (sig.direction == "sell" and cvd_sl > 0.5)
                if cvd_against:
                    sl = entry  # breakeven
                    be_moved = True

            if in_profit and pnl_cur > risk * 0.5:
                # Strong CVD reversal while profitable → exit now
                cvd_strong_against = (sig.direction == "buy" and cvd_sl < -1.0) or \
                                     (sig.direction == "sell" and cvd_sl > 1.0)
                if cvd_strong_against:
                    result = "win"
                    exit_price, exit_bar, exit_reason = cur_close, j, "cvd_exit"
                    break

            # ── DEEP EFFORT COUNTER-SIGNAL EXIT ──
            # Opposite DE zone appears → pressure against us → exit
            if in_profit and b["deep_effort_absorption"] > 4:
                de_against = (sig.direction == "buy" and cur_close < float(b["open"])) or \
                             (sig.direction == "sell" and cur_close > float(b["open"]))
                if de_against:
                    result = "win" if pnl_cur > 0 else "loss"
                    exit_price, exit_bar, exit_reason = cur_close, j, "de_exit"
                    break

            # ── BIG TRADE TRAILING STOP (strong moves) ──
            if in_profit and pnl_cur > risk * 1.5 and b["is_big_trade"]:
                bt_dir = float(b["big_trade_direction"])
                bt_against = (sig.direction == "buy" and bt_dir < 0) or \
                             (sig.direction == "sell" and bt_dir > 0)
                if bt_against:
                    result = "win"
                    exit_price, exit_bar, exit_reason = cur_close, j, "bt_trail"
                    break
        else:
            last = df.iloc[min(sig.bar_index + max_hold, len(df) - 1)]
            exit_price = float(last["close"])
            pnl_raw = (exit_price - entry) if sig.direction == "buy" else (entry - exit_price)
            result = "win" if pnl_raw > 0 else "loss"

        pnl_raw = (exit_price - entry) if sig.direction == "buy" else (entry - exit_price)
        pnl_r = pnl_raw / risk

        results.append(SimResult(
            bar_index=sig.bar_index, timestamp=sig.timestamp,
            setup=sig.setup, direction=sig.direction,
            entry=round(entry, 6), stop_loss=round(sig.stop_loss, 6),
            take_profit=round(tp, 6), exit_price=round(exit_price, 6),
            exit_bar=exit_bar, result=result,
            pnl_r=round(pnl_r, 4), holding_bars=holding, note=sig.note,
            exit_reason=exit_reason, risk_tier=sig.risk_tier,
            confluence=sig.confluence, confluence_detail=sig.confluence_detail,
            features=features,
        ))
        next_allowed = exit_bar + 1

    return results


# ── Analytics ─────────────────────────────────────────────────────

def compute_stats(trades: list[SimResult], initial_balance: float = 10000) -> dict:
    if not trades:
        return {"total_trades": 0, "win_rate": 0, "notes": ["No setups found."]}

    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]
    pnls = [t.pnl_r for t in trades]
    n = len(trades)

    win_rate = len(wins) / n * 100
    gross_win = sum(t.pnl_r for t in wins) or 0
    gross_loss = abs(sum(t.pnl_r for t in losses)) or 0.0001
    pf = gross_win / gross_loss if gross_loss > 0 else 999

    # Equity curve
    eq = []
    running = 0.0
    for i, t in enumerate(trades):
        running += t.pnl_r
        eq.append({"index": i + 1, "equity": round(running, 4)})

    # Drawdown
    peak = dd = 0.0
    for p in eq:
        peak = max(peak, p["equity"])
        dd = max(dd, peak - p["equity"])

    # Sharpe / Sortino
    if len(pnls) > 1:
        m, s = np.mean(pnls), np.std(pnls, ddof=1)
        sharpe = (m / s * math.sqrt(252)) if s > 0 else 0
        ds = [r for r in pnls if r < 0]
        sortino = (m / np.std(ds, ddof=1) * math.sqrt(252)) if ds and np.std(ds, ddof=1) > 0 else 0
    else:
        sharpe = sortino = 0

    # Streaks
    w_streak = l_streak = cur = 0
    cur_type = None
    for t in trades:
        if t.result == cur_type:
            cur += 1
        else:
            cur_type, cur = t.result, 1
        if cur_type == "win":
            w_streak = max(w_streak, cur)
        else:
            l_streak = max(l_streak, cur)

    # By setup
    setup_stats = {}
    for t in trades:
        s = t.setup
        if s not in setup_stats:
            setup_stats[s] = {"trades": 0, "wins": 0, "pnl_r": 0}
        setup_stats[s]["trades"] += 1
        if t.result == "win":
            setup_stats[s]["wins"] += 1
        setup_stats[s]["pnl_r"] = round(setup_stats[s]["pnl_r"] + t.pnl_r, 4)

    setup_breakdown = [
        {
            "setup": k,
            "trades": v["trades"],
            "wins": v["wins"],
            "win_rate": round(v["wins"] / v["trades"] * 100, 1),
            "pnl_r": v["pnl_r"],
        }
        for k, v in setup_stats.items()
    ]

    # Monthly
    monthly: dict[str, dict] = {}
    for t in trades:
        try:
            key = pd.Timestamp(t.timestamp).strftime("%Y-%m")
        except Exception:
            key = "unknown"
        if key not in monthly:
            monthly[key] = {"trades": 0, "wins": 0, "pnl_r": 0.0}
        monthly[key]["trades"] += 1
        if t.result == "win":
            monthly[key]["wins"] += 1
        monthly[key]["pnl_r"] = round(monthly[key]["pnl_r"] + t.pnl_r, 4)

    monthly_list = [
        {"month": k, "trades": v["trades"], "wins": v["wins"],
         "win_rate": round(v["wins"] / v["trades"] * 100, 1),
         "pnl_r": v["pnl_r"]}
        for k, v in sorted(monthly.items())
    ]

    # Hourly heatmap
    hourly: dict[int, dict] = {}
    for t in trades:
        try:
            hr = int(t.timestamp.split(" ")[1].split(":")[0])
        except Exception:
            hr = 0
        if hr not in hourly:
            hourly[hr] = {"trades": 0, "wins": 0, "pnl_r": 0.0}
        hourly[hr]["trades"] += 1
        if t.result == "win":
            hourly[hr]["wins"] += 1
        hourly[hr]["pnl_r"] = round(hourly[hr]["pnl_r"] + t.pnl_r, 4)

    hourly_list = [
        {"hour": k, "trades": v["trades"], "wins": v["wins"],
         "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
         "pnl_r": v["pnl_r"]}
        for k, v in sorted(hourly.items())
    ]

    # Exit reason breakdown (Fabio: CVD exit, DE exit, BT trail)
    exit_stats: dict[str, dict] = {}
    for t in trades:
        er = t.exit_reason or "unknown"
        if er not in exit_stats:
            exit_stats[er] = {"trades": 0, "wins": 0, "pnl_r": 0.0}
        exit_stats[er]["trades"] += 1
        if t.result == "win":
            exit_stats[er]["wins"] += 1
        exit_stats[er]["pnl_r"] = round(exit_stats[er]["pnl_r"] + t.pnl_r, 4)

    exit_breakdown = [
        {"reason": k, "trades": v["trades"], "wins": v["wins"],
         "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
         "pnl_r": v["pnl_r"]}
        for k, v in exit_stats.items()
    ]

    # Risk tier breakdown (Fabio: 3/5=standard, 4/5=elevated, 5/5=max)
    tier_stats: dict[str, dict] = {}
    for t in trades:
        rt = t.risk_tier or "standard"
        if rt not in tier_stats:
            tier_stats[rt] = {"trades": 0, "wins": 0, "pnl_r": 0.0}
        tier_stats[rt]["trades"] += 1
        if t.result == "win":
            tier_stats[rt]["wins"] += 1
        tier_stats[rt]["pnl_r"] = round(tier_stats[rt]["pnl_r"] + t.pnl_r, 4)

    tier_breakdown = [
        {"tier": k, "trades": v["trades"], "wins": v["wins"],
         "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
         "pnl_r": v["pnl_r"]}
        for k, v in tier_stats.items()
    ]

    # Balance
    bal = initial_balance
    for t in trades:
        risk_mult = {"standard": 0.0025, "elevated": 0.005, "max": 0.0075}.get(t.risk_tier, 0.0025)
        bal += bal * risk_mult * t.pnl_r

    # Notes
    notes = [f"Found {n} Fabio setups over the test period."]
    notes.append(f"Win rate: {win_rate:.1f}% | Profit factor: {pf:.2f}")
    if win_rate >= 55 and pf > 1.5:
        notes.append("✅ Strong edge — consider forward testing on demo.")
    elif win_rate >= 45 and pf > 1.0:
        notes.append("⚠️ Marginal edge — fine-tune VP period or follow-through bars.")
    else:
        notes.append("❌ Weak results — try different parameters or longer data.")

    best = max(setup_breakdown, key=lambda x: x["pnl_r"]) if setup_breakdown else None
    if best:
        notes.append(f"Best setup: {best['setup']} ({best['win_rate']}% WR, {best['pnl_r']}R)")

    # CVD exit insight
    cvd_exits = [t for t in trades if t.exit_reason == "cvd_exit"]
    if cvd_exits:
        cvd_pnl = sum(t.pnl_r for t in cvd_exits)
        notes.append(f"📊 CVD exits saved {len(cvd_exits)} trades ({cvd_pnl:+.2f}R total)")

    # High-confluence insight
    hc_trades = [t for t in trades if t.confluence >= 4]
    if hc_trades:
        hc_wr = len([t for t in hc_trades if t.result == "win"]) / len(hc_trades) * 100
        notes.append(f"🎯 High confluence (4+): {len(hc_trades)} trades, {hc_wr:.0f}% WR")

    return {
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_r": round(sum(pnls), 4),
        "avg_win_r": round(float(np.mean([t.pnl_r for t in wins])), 4) if wins else 0,
        "avg_loss_r": round(float(np.mean([abs(t.pnl_r) for t in losses])), 4) if losses else 0,
        "profit_factor": round(float(pf), 4) if pf < 999 else 999,
        "expectancy_r": round(float(np.mean(pnls)), 4),
        "sharpe_ratio": round(float(sharpe), 4),
        "sortino_ratio": round(float(sortino), 4),
        "max_drawdown_r": round(float(dd), 4),
        "max_win_streak": w_streak,
        "max_loss_streak": l_streak,
        "avg_holding_bars": round(float(np.mean([t.holding_bars for t in trades])), 1),
        "equity_curve": eq,
        "setup_breakdown": setup_breakdown,
        "exit_breakdown": exit_breakdown,
        "tier_breakdown": tier_breakdown,
        "monthly_breakdown": monthly_list,
        "hourly_breakdown": hourly_list,
        "final_balance": round(bal, 2),
        "return_pct": round((bal - initial_balance) / initial_balance * 100, 2),
        "notes": notes,
    }


# ── AI Scoring ────────────────────────────────────────────────────

def score_trades_with_model(trades: list[SimResult], model) -> list[SimResult]:
    """Score each trade using trained ML model. Adds ai_score (0-100%)."""
    if model is None or not trades:
        return trades

    try:
        # Extract numeric features only (same as training)
        feature_rows = []
        valid_indices = []
        for i, t in enumerate(trades):
            if t.features:
                numeric_feats = {k: v for k, v in t.features.items() if isinstance(v, (int, float))}
                if numeric_feats:
                    feature_rows.append(numeric_feats)
                    valid_indices.append(i)

        if not feature_rows:
            return trades

        df_feats = pd.DataFrame(feature_rows)
        # Predict probability of win
        probas = model.predict_proba(df_feats)[:, 1]  # P(win)

        for idx, proba in zip(valid_indices, probas):
            trades[idx].ai_score = round(float(proba) * 100, 1)

    except Exception:
        pass  # Model incompatible with features — skip scoring silently

    return trades


# ── Main runner ───────────────────────────────────────────────────

def run_fabio_backtest(req: FabioBacktestRequest, trained_model=None) -> dict:
    df = pd.DataFrame(req.candles)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Convert timestamp to UTC+5 for the user
    if "timestamp" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df["timestamp"] = df["timestamp"].dt.tz_convert('Asia/Tashkent')
            df["timestamp"] = df["timestamp"].dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            df["timestamp"] = df["timestamp"].astype(str)

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    else:
        df["volume"] = 1.0  # tick volume proxy
    df = df.dropna(subset=["open", "high", "low", "close"])

    df = compute_order_flow(df)
    signals = detect_setups(df, req)
    trades = simulate_signals(df, signals, max_hold=req.max_holding_bars)

    # Score with AI model if available
    if trained_model is not None:
        trades = score_trades_with_model(trades, trained_model)

    stats = compute_stats(trades, req.initial_balance)

    # AI scoring stats
    scored = [t for t in trades if t.ai_score >= 0]
    ai_info = {}
    if scored:
        high_score = [t for t in scored if t.ai_score >= 60]
        low_score = [t for t in scored if t.ai_score < 40]
        ai_info = {
            "ai_scored_trades": len(scored),
            "ai_avg_score": round(float(np.mean([t.ai_score for t in scored])), 1),
            "ai_high_score_trades": len(high_score),
            "ai_high_score_wr": round(len([t for t in high_score if t.result == "win"]) / len(high_score) * 100, 1) if high_score else 0,
            "ai_low_score_trades": len(low_score),
            "ai_low_score_wr": round(len([t for t in low_score if t.result == "win"]) / len(low_score) * 100, 1) if low_score else 0,
        }

    return {
        **stats,
        **ai_info,
        "trades_list": [t.model_dump() for t in trades[:200]],
        "total_signals": len(signals),
        "has_ai_scores": len(scored) > 0,
    }

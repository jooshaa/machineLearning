"""Advanced backtesting engine with technical indicators and comprehensive analytics."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd
import ta
import yfinance as yf
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class FetchCandlesRequest(BaseModel):
    symbol: str  # e.g. "EURUSD=X", "BTCUSD", "AAPL"
    interval: str = "1h"  # 1m,5m,15m,30m,1h,4h,1d,1wk
    period: str | None = "6mo"  # 1d,5d,1mo,3mo,6mo,1y,2y,5y,max
    start: str | None = None
    end: str | None = None


class IndicatorCondition(BaseModel):
    indicator: str  # sma_20, ema_50, rsi_14, macd_signal, bb_upper, etc.
    operator: Literal["above", "below", "crosses_above", "crosses_below"]
    value: float | str | None = None  # fixed numeric or another indicator name


class AdvancedBacktestRequest(BaseModel):
    candles: list[dict]
    direction: Literal["buy", "sell"] = "buy"
    entry_conditions: list[IndicatorCondition] = []
    exit_conditions: list[IndicatorCondition] = []
    stop_loss_atr_mult: float = 1.5  # SL = entry ± ATR * mult
    take_profit_atr_mult: float = 3.0  # TP = entry ± ATR * mult
    risk_per_trade: float = 1.0  # position size in R
    forward_bars: int = 20  # max holding period
    initial_balance: float = 10000.0


# ---------------------------------------------------------------------------
# Data fetcher
# ---------------------------------------------------------------------------

INTERVAL_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "1h",  # yfinance doesn't support 4h — we'll resample
    "D1": "1d",
    "W1": "1wk",
}

SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SPX500": "^GSPC",
    "NAS100": "^IXIC",
    "US30": "^DJI",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "GOLD": "GC=F",
    "NQ": "NQ=F",
    "ES": "ES=F",
    "NQ.FUT": "NQ=F",
    "ES.FUT": "ES=F",
}


def fetch_candles(request: FetchCandlesRequest) -> list[dict]:
    """Fetch OHLCV data from Yahoo Finance."""
    symbol = SYMBOL_MAP.get(request.symbol.upper(), request.symbol)
    yf_interval = INTERVAL_MAP.get(request.interval.upper(), request.interval)
    needs_resample = request.interval.upper() == "H4"
    period = request.period
    
    # Yahoo Finance Limits:
    # 1m: max 7d
    # 5m/15m/30m: max 60d
    # 1h: max 730d
    if yf_interval in ["1m", "2m", "5m", "15m", "30m", "90m"]:
        if "mo" in period or "y" in period:
            print(f"⚠️ Period {period} is too long for interval {yf_interval}. Capping to 1mo.")
            period = "1mo"
            
    print(f"📥 Fetching Candles: {symbol} | {yf_interval} | {period or 'start=' + str(request.start)}")
    ticker = yf.Ticker(symbol)
    
    if request.start and request.end:
        df = ticker.history(start=request.start, end=request.end, interval=yf_interval)
    else:
        df = ticker.history(period=period, interval=yf_interval)

    if df.empty:
        return []

    if needs_resample:
        df = df.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }).dropna()

    df = df.reset_index()
    date_col = "Datetime" if "Datetime" in df.columns else "Date"

    records = []
    for _, row in df.iterrows():
        records.append({
            "timestamp": str(row[date_col]),
            "open": round(float(row["Open"]), 6),
            "high": round(float(row["High"]), 6),
            "low": round(float(row["Low"]), 6),
            "close": round(float(row["Close"]), 6),
            "volume": int(row.get("Volume", 0)),
        })

    return records


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to the candle dataframe."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Moving Averages
    for period in [10, 20, 50, 100, 200]:
        df[f"sma_{period}"] = ta.trend.sma_indicator(close, window=period)
        df[f"ema_{period}"] = ta.trend.ema_indicator(close, window=period)

    # RSI
    for period in [7, 14, 21]:
        df[f"rsi_{period}"] = ta.momentum.rsi(close, window=period)

    # ATR
    for period in [7, 14]:
        df[f"atr_{period}"] = ta.volatility.average_true_range(high, low, close, window=period)

    # MACD
    macd = ta.trend.MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()

    # Stochastic
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # ADX
    adx = ta.trend.ADXIndicator(high, low, close, window=14)
    df["adx"] = adx.adx()

    # Volume SMA (if volume exists)
    if "volume" in df.columns:
        df["volume_sma_20"] = ta.trend.sma_indicator(
            df["volume"].astype(float), window=20
        )

    return df


# ---------------------------------------------------------------------------
# Condition evaluator
# ---------------------------------------------------------------------------

def resolve_indicator_value(df: pd.DataFrame, idx: int, ref: str | float | None) -> float | None:
    """Resolve a value — could be a column name or a numeric literal."""
    if ref is None:
        return None
    if isinstance(ref, (int, float)):
        return float(ref)
    if isinstance(ref, str):
        # Try as number first
        try:
            return float(ref)
        except ValueError:
            pass
        # Column reference
        if ref in df.columns and idx < len(df):
            val = df.iloc[idx][ref]
            return float(val) if pd.notna(val) else None
        # Also treat "close", "open", etc. as column refs
        if ref.lower() in df.columns:
            val = df.iloc[idx][ref.lower()]
            return float(val) if pd.notna(val) else None
    return None


def evaluate_condition(
    df: pd.DataFrame, idx: int, condition: IndicatorCondition
) -> bool:
    """Evaluate a single indicator condition at a given bar index."""
    if idx < 1 or idx >= len(df):
        return False

    indicator_col = condition.indicator.lower()
    if indicator_col not in df.columns:
        return False

    current = df.iloc[idx][indicator_col]
    previous = df.iloc[idx - 1][indicator_col]
    if pd.isna(current) or pd.isna(previous):
        return False

    current = float(current)
    previous = float(previous)

    # Resolve comparison value
    compare = resolve_indicator_value(df, idx, condition.value)
    if compare is None:
        # For cross conditions, compare might be another indicator
        if isinstance(condition.value, str) and condition.value.lower() in df.columns:
            compare = float(df.iloc[idx][condition.value.lower()])
            compare_prev = float(df.iloc[idx - 1][condition.value.lower()])
        else:
            return False
    else:
        compare_prev = resolve_indicator_value(df, idx - 1, condition.value)
        if compare_prev is None:
            compare_prev = compare

    if condition.operator == "above":
        return current > compare
    elif condition.operator == "below":
        return current < compare
    elif condition.operator == "crosses_above":
        return previous <= compare_prev and current > compare
    elif condition.operator == "crosses_below":
        return previous >= compare_prev and current < compare

    return False


def evaluate_conditions(
    df: pd.DataFrame, idx: int, conditions: list[IndicatorCondition]
) -> bool:
    """All conditions must be true (AND logic)."""
    if not conditions:
        return False
    return all(evaluate_condition(df, idx, c) for c in conditions)


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

class SimulatedTrade(BaseModel):
    timestamp: str
    bar_index: int
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_bar: int
    result: Literal["win", "loss"]
    pnl_r: float
    holding_bars: int


def simulate_advanced(
    df: pd.DataFrame, request: AdvancedBacktestRequest
) -> list[SimulatedTrade]:
    """Run the backtest simulation with indicator-based entry rules."""
    trades: list[SimulatedTrade] = []
    in_trade = False
    min_start = 200  # need enough bars for indicator warmup

    for i in range(min_start, len(df) - 1):
        if in_trade:
            continue

        # Check entry conditions
        if not evaluate_conditions(df, i, request.entry_conditions):
            continue

        # We have a signal — compute SL/TP from ATR
        atr_col = "atr_14" if "atr_14" in df.columns else None
        if atr_col and pd.notna(df.iloc[i][atr_col]):
            atr = float(df.iloc[i][atr_col])
        else:
            # Fallback: use range of last 14 bars
            window = df.iloc[max(0, i - 14):i]
            atr = float((window["high"] - window["low"]).mean()) if len(window) > 0 else 0.001

        entry = float(df.iloc[i]["close"])
        if request.direction == "buy":
            sl = entry - atr * request.stop_loss_atr_mult
            tp = entry + atr * request.take_profit_atr_mult
        else:
            sl = entry + atr * request.stop_loss_atr_mult
            tp = entry - atr * request.take_profit_atr_mult

        # Walk forward to resolve trade
        result = "loss"
        exit_price = sl
        exit_bar = min(i + request.forward_bars, len(df) - 1)
        holding = 0

        for j in range(i + 1, min(i + 1 + request.forward_bars, len(df))):
            holding = j - i
            bar = df.iloc[j]

            if request.direction == "buy":
                if float(bar["low"]) <= sl:
                    result = "loss"
                    exit_price = sl
                    exit_bar = j
                    break
                if float(bar["high"]) >= tp:
                    result = "win"
                    exit_price = tp
                    exit_bar = j
                    break
            else:
                if float(bar["high"]) >= sl:
                    result = "loss"
                    exit_price = sl
                    exit_bar = j
                    break
                if float(bar["low"]) <= tp:
                    result = "win"
                    exit_price = tp
                    exit_bar = j
                    break

            # Check exit conditions
            if request.exit_conditions and evaluate_conditions(df, j, request.exit_conditions):
                actual_pnl = (float(bar["close"]) - entry) if request.direction == "buy" else (entry - float(bar["close"]))
                result = "win" if actual_pnl > 0 else "loss"
                exit_price = float(bar["close"])
                exit_bar = j
                break
        else:
            # Max holding period reached — close at last bar
            last = df.iloc[min(i + request.forward_bars, len(df) - 1)]
            exit_price = float(last["close"])
            actual_pnl = (exit_price - entry) if request.direction == "buy" else (entry - exit_price)
            result = "win" if actual_pnl > 0 else "loss"

        # Calculate PnL in R
        risk = abs(entry - sl) if abs(entry - sl) > 0 else 0.0001
        actual_pnl_price = (exit_price - entry) if request.direction == "buy" else (entry - exit_price)
        pnl_r = actual_pnl_price / risk

        timestamp = str(df.iloc[i].get("timestamp", str(i)))

        trades.append(SimulatedTrade(
            timestamp=timestamp,
            bar_index=i,
            entry=round(entry, 6),
            stop_loss=round(sl, 6),
            take_profit=round(tp, 6),
            exit_price=round(exit_price, 6),
            exit_bar=exit_bar,
            result=result,
            pnl_r=round(pnl_r, 4),
            holding_bars=holding,
        ))

        in_trade = True
        # Release trade after exit bar for next signal
        # Simple: skip forward to exit_bar
        # We use in_trade flag and reset after processing

    # Since we can't modify loop index in Python, do second pass
    # Actually let's redo with proper skip logic
    return _simulate_with_skip(df, request, min_start)


def _simulate_with_skip(
    df: pd.DataFrame, request: AdvancedBacktestRequest, min_start: int
) -> list[SimulatedTrade]:
    """Simulate with proper trade skipping (no overlapping positions)."""
    trades: list[SimulatedTrade] = []
    next_allowed = min_start

    for i in range(min_start, len(df) - 1):
        if i < next_allowed:
            continue

        if not evaluate_conditions(df, i, request.entry_conditions):
            continue

        atr_col = "atr_14" if "atr_14" in df.columns else None
        if atr_col and pd.notna(df.iloc[i][atr_col]):
            atr = float(df.iloc[i][atr_col])
        else:
            window = df.iloc[max(0, i - 14):i]
            atr = float((window["high"] - window["low"]).mean()) if len(window) > 0 else 0.001

        entry = float(df.iloc[i]["close"])
        if request.direction == "buy":
            sl = entry - atr * request.stop_loss_atr_mult
            tp = entry + atr * request.take_profit_atr_mult
        else:
            sl = entry + atr * request.stop_loss_atr_mult
            tp = entry - atr * request.take_profit_atr_mult

        result = "loss"
        exit_price = sl
        exit_bar = min(i + request.forward_bars, len(df) - 1)
        holding = 0

        for j in range(i + 1, min(i + 1 + request.forward_bars, len(df))):
            holding = j - i
            bar = df.iloc[j]

            if request.direction == "buy":
                if float(bar["low"]) <= sl:
                    result = "loss"
                    exit_price = sl
                    exit_bar = j
                    break
                if float(bar["high"]) >= tp:
                    result = "win"
                    exit_price = tp
                    exit_bar = j
                    break
            else:
                if float(bar["high"]) >= sl:
                    result = "loss"
                    exit_price = sl
                    exit_bar = j
                    break
                if float(bar["low"]) <= tp:
                    result = "win"
                    exit_price = tp
                    exit_bar = j
                    break

            if request.exit_conditions and evaluate_conditions(df, j, request.exit_conditions):
                actual_pnl = (float(bar["close"]) - entry) if request.direction == "buy" else (entry - float(bar["close"]))
                result = "win" if actual_pnl > 0 else "loss"
                exit_price = float(bar["close"])
                exit_bar = j
                break
        else:
            last = df.iloc[min(i + request.forward_bars, len(df) - 1)]
            exit_price = float(last["close"])
            actual_pnl = (exit_price - entry) if request.direction == "buy" else (entry - exit_price)
            result = "win" if actual_pnl > 0 else "loss"

        risk = abs(entry - sl) if abs(entry - sl) > 0 else 0.0001
        actual_pnl_price = (exit_price - entry) if request.direction == "buy" else (entry - exit_price)
        pnl_r = actual_pnl_price / risk

        timestamp = str(df.iloc[i].get("timestamp", str(i)))

        trades.append(SimulatedTrade(
            timestamp=timestamp,
            bar_index=i,
            entry=round(entry, 6),
            stop_loss=round(sl, 6),
            take_profit=round(tp, 6),
            exit_price=round(exit_price, 6),
            exit_bar=exit_bar,
            result=result,
            pnl_r=round(pnl_r, 4),
            holding_bars=holding,
        ))

        next_allowed = exit_bar + 1

    return trades


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_analytics(
    trades: list[SimulatedTrade], initial_balance: float = 10000.0
) -> dict:
    """Compute comprehensive backtest statistics."""
    if not trades:
        return _empty_analytics()

    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]
    pnl_list = [t.pnl_r for t in trades]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    total_r = sum(pnl_list)
    avg_win = np.mean([t.pnl_r for t in wins]) if wins else 0
    avg_loss = np.mean([abs(t.pnl_r) for t in losses]) if losses else 0
    gross_profit = sum(t.pnl_r for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_r for t in losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    expectancy = total_r / total_trades if total_trades > 0 else 0

    # Equity curve
    equity_curve = []
    running = 0.0
    for idx, t in enumerate(trades):
        running += t.pnl_r
        equity_curve.append({"index": idx + 1, "equity": round(running, 4)})

    # Max drawdown
    peak = 0.0
    max_dd = 0.0
    for point in equity_curve:
        if point["equity"] > peak:
            peak = point["equity"]
        dd = peak - point["equity"]
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (daily-ish)
    if len(pnl_list) > 1:
        mean_r = np.mean(pnl_list)
        std_r = np.std(pnl_list, ddof=1)
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0
    else:
        sharpe = 0

    # Sortino ratio
    downside = [r for r in pnl_list if r < 0]
    if downside and len(pnl_list) > 1:
        downside_std = np.std(downside, ddof=1)
        sortino = (np.mean(pnl_list) / downside_std * math.sqrt(252)) if downside_std > 0 else 0
    else:
        sortino = 0

    # Win/loss streaks
    max_win_streak = 0
    max_loss_streak = 0
    current_streak = 0
    streak_type = None
    for t in trades:
        if t.result == streak_type:
            current_streak += 1
        else:
            streak_type = t.result
            current_streak = 1
        if streak_type == "win":
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)

    # Monthly breakdown
    monthly: dict[str, dict] = {}
    for t in trades:
        try:
            dt = pd.Timestamp(t.timestamp)
            key = dt.strftime("%Y-%m")
        except Exception:
            key = "unknown"
        if key not in monthly:
            monthly[key] = {"trades": 0, "wins": 0, "pnl_r": 0.0}
        monthly[key]["trades"] += 1
        if t.result == "win":
            monthly[key]["wins"] += 1
        monthly[key]["pnl_r"] = round(monthly[key]["pnl_r"] + t.pnl_r, 4)

    monthly_list = [
        {
            "month": k,
            "trades": v["trades"],
            "wins": v["wins"],
            "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] > 0 else 0,
            "pnl_r": v["pnl_r"],
        }
        for k, v in sorted(monthly.items())
    ]

    # Holding period stats
    avg_holding = np.mean([t.holding_bars for t in trades]) if trades else 0

    # Balance curve (percentage)
    balance_curve = []
    balance = initial_balance
    for t in trades:
        pnl_dollar = balance * 0.01 * t.pnl_r  # 1% risk per R
        balance += pnl_dollar
        balance_curve.append(round(balance, 2))

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 2),
        "total_r": round(total_r, 4),
        "avg_win_r": round(float(avg_win), 4),
        "avg_loss_r": round(float(avg_loss), 4),
        "profit_factor": round(float(profit_factor), 4) if profit_factor != float("inf") else 999.0,
        "expectancy_r": round(float(expectancy), 4),
        "sharpe_ratio": round(float(sharpe), 4),
        "sortino_ratio": round(float(sortino), 4),
        "max_drawdown_r": round(float(max_dd), 4),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "avg_holding_bars": round(float(avg_holding), 1),
        "equity_curve": equity_curve,
        "monthly_breakdown": monthly_list,
        "final_balance": round(balance, 2),
        "return_pct": round((balance - initial_balance) / initial_balance * 100, 2),
    }


def _empty_analytics() -> dict:
    return {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0,
        "total_r": 0,
        "avg_win_r": 0,
        "avg_loss_r": 0,
        "profit_factor": 0,
        "expectancy_r": 0,
        "sharpe_ratio": 0,
        "sortino_ratio": 0,
        "max_drawdown_r": 0,
        "max_win_streak": 0,
        "max_loss_streak": 0,
        "avg_holding_bars": 0,
        "equity_curve": [],
        "monthly_breakdown": [],
        "final_balance": 0,
        "return_pct": 0,
    }


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

def run_advanced_backtest(request: AdvancedBacktestRequest) -> dict:
    """Full pipeline: candles → indicators → simulate → analytics."""
    df = pd.DataFrame(request.candles)

    # Ensure numeric columns
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    df = df.dropna(subset=["open", "high", "low", "close"])

    if len(df) < 250:
        # Still try but warn
        pass

    # Compute indicators
    df = compute_indicators(df)

    # Run simulation
    trades = _simulate_with_skip(df, request, min_start=min(200, len(df) - 2))

    # Compute analytics
    analytics = compute_analytics(trades, request.initial_balance)

    # Build notes
    notes = _build_notes(trades, analytics, request)

    return {
        **analytics,
        "trades_list": [t.model_dump() for t in trades[:100]],  # cap at 100 for response size
        "total_signals": len(trades),
        "notes": notes,
        "direction": request.direction,
        "stop_loss_atr_mult": request.stop_loss_atr_mult,
        "take_profit_atr_mult": request.take_profit_atr_mult,
    }


def _build_notes(
    trades: list[SimulatedTrade], analytics: dict, request: AdvancedBacktestRequest
) -> list[str]:
    notes = []

    if not trades:
        notes.append("No qualifying setups found with the selected indicator conditions.")
        notes.append("Try adjusting your entry rules or using a longer data period.")
        return notes

    wr = analytics["win_rate"]
    pf = analytics["profit_factor"]
    exp = analytics["expectancy_r"]

    notes.append(f"Found {len(trades)} trade signals over the test period.")
    notes.append(f"Win rate: {wr}% | Profit factor: {pf} | Expectancy: {exp}R per trade.")

    if wr >= 55 and pf > 1.5:
        notes.append("✅ This strategy shows strong edge — consider forward testing on a demo account.")
    elif wr >= 45 and pf > 1.0:
        notes.append("⚠️ Marginal edge detected. Fine-tune entry filters or risk management.")
    else:
        notes.append("❌ This rule set is currently unprofitable. Review conditions and market context.")

    if analytics["max_drawdown_r"] > 10:
        notes.append("⚠️ High drawdown detected — consider tighter stop losses or position sizing.")

    if analytics["avg_holding_bars"] > request.forward_bars * 0.8:
        notes.append("Many trades hit max holding period — the strategy may need cleaner exit rules.")

    return notes

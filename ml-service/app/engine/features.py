import pandas as pd
import numpy as np


def extract_l3_features(mbo_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts advanced Level 3 (MBO) order flow features and events.
    mbo_df: Raw MBO databento data (to track spoofs, cancels)
    events_df: The Trade events enriched with L3 snapshots from OrderBookL3
    """
    if events_df.empty:
        return pd.DataFrame()

    df = events_df.copy()

    # 1. Base liquidity features
    df["orderbook_imbalance"] = df["total_bid_liquidity"] / (
        df["total_ask_liquidity"] + 1e-9
    )
    df["liquidity_pressure"] = df["total_bid_liquidity"] - df["total_ask_liquidity"]

    # We need to compute delta over a rolling window of events
    df["delta"] = np.where(df["side"] == "A", df["size"], -df["size"])
    df["cvd"] = df["delta"].cumsum()
    df["cvd_baseline"] = df["delta"].rolling(50, min_periods=5).std().fillna(0)

    # 2. True Absorption Detection
    # Maximum sensitivity for discovery
    rolling_vol_30 = df["size"].rolling(30).sum()
    delta_30 = df["delta"].rolling(30).sum()
    price_range_30 = df["price"].rolling(30).apply(lambda x: x.max() - x.min(), raw=True)
    price_range_mean = price_range_30.rolling(30, min_periods=5).mean()
    rolling_vol_mean = rolling_vol_30.rolling(30, min_periods=5).mean()

    df["absorption_flag"] = (
        (rolling_vol_30 > rolling_vol_mean * 1.2) &
        (abs(delta_30) > rolling_vol_30 * 0.015) &
        (price_range_30 < price_range_mean * 1.2)
    )
    df["absorption_strength"] = np.where(df["absorption_flag"], abs(delta_30), 0.0)

    # 3. True Trap Detection
    rolling_high_30 = df["price"].rolling(30).max().shift(1)
    rolling_low_30 = df["price"].rolling(30).min().shift(1)
    df["is_breakout"] = (df["price"] > rolling_high_30) | (df["price"] < rolling_low_30)

    df["trap_flag"] = (
        df["is_breakout"] &
        (abs(delta_30) > rolling_vol_30 * 0.01) &
        (price_range_30 < price_range_mean * 0.4)
    )
    df["trap_strength"] = np.where(df["trap_flag"], abs(delta_30), 0.0)

    # Event type priorities
    df["rolling_vol_mean"] = rolling_vol_mean

    # 4. Spoofing Detection (Analyzed on raw MBO data)
    # large_order_added and lifetime < threshold_ms and not traded
    # We will build an aggregate metric of spoofing activity and merge it
    if "action" in mbo_df.columns:
        mbo = mbo_df.copy()
        mbo["ts_recv"] = mbo.index
        # Add events
        adds = mbo[mbo["action"] == "A"][
            ["order_id", "size", "price", "ts_recv", "side"]
        ]
        # Cancel events
        cancels = mbo[mbo["action"] == "C"][["order_id", "ts_recv"]]

        # Merge to find lifetimes
        merged = pd.merge(
            adds, cancels, on="order_id", suffixes=("_add", "_cancel"), how="inner"
        )
        merged["lifetime"] = (
            merged["ts_recv_cancel"] - merged["ts_recv_add"]
        ).dt.total_seconds()

        # Spoofing criteria: size > 90th percentile, lifetime < 1.0 seconds
        size_threshold = merged["size"].quantile(0.9)
        merged["is_spoof"] = (merged["size"] >= size_threshold) & (
            merged["lifetime"] < 1.0
        )

        spoofs = merged[merged["is_spoof"]].copy()

        # Count spoofs over 1 minute rolling windows
        spoofs.set_index("ts_recv_add", inplace=True)
        spoof_counts = spoofs.resample("1s").size().rename("spoof_activity")

        # Reindex to match events_df
        df = df.set_index("ts")
        # join asof or resample. Because events_df index is datetime, we can merge_asof
        df = pd.merge_asof(
            df.sort_index(),
            spoof_counts.sort_index(),
            left_index=True,
            right_index=True,
            direction="backward",
            tolerance=pd.Timedelta("1s"),
        )
        df["spoof_activity"] = df["spoof_activity"].fillna(0)
    else:
        df["spoof_activity"] = 0.0

    # D1: CVD divergence (RELAXED FOR ML DISCOVERY)

    df["price_slope"] = (
        df["price"]
        .rolling(5)
        .apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0]
            if len(x) == 5 else 0
        )
    )

    df["cvd_slope"] = (
        df["cvd"]
        .rolling(5)
        .apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0]
            if len(x) == 5 else 0
        )
    )

    cvd_div = np.zeros(len(df))

    # Bearish divergence
    cvd_div[
        (df["price_slope"] >= -0.5) &
        (df["cvd_slope"] < -1)
    ] = -1

    # Bullish divergence
    cvd_div[
        (df["price_slope"] <= 0.5) &
        (df["cvd_slope"] > 1)
    ] = 1

    df["cvd_divergence"] = cvd_div

    # Extra relaxed participation logic
    df["delta_velocity"] = (
        df["cvd"]
        .diff()
        .rolling(3)
        .mean()
        .fillna(0)
    )

    df["participation_event"] = (
        (abs(df["cvd_slope"]) > 1) |
        (abs(df["price_slope"]) > 0.2)
    ).astype(int)

    print(f"[DEBUG] participation events: {df['participation_event'].sum()}")
    print(f"[DEBUG] bullish divs: {(df['cvd_divergence'] == 1).sum()}")
    print(f"[DEBUG] bearish divs: {(df['cvd_divergence'] == -1).sum()}")

    # C2: UNCLEAR thresholds (volume profile std)
    df["vp_std"] = df["size"].rolling(20, min_periods=5).std().fillna(0)
    df["vp_std_mean"] = df["vp_std"].rolling(20, min_periods=5).mean().fillna(0)
    df["cvd_slope_std"] = df["cvd_slope"].rolling(20, min_periods=5).std().fillna(0)

    # D3: Swing detection for Fixed Profile
    df["swing_high"] = df["price"].rolling(5).max().rolling(50, min_periods=10).max()
    df["swing_low"] = df["price"].rolling(5).min().rolling(50, min_periods=10).min()

    df["event_type"] = "normal"
    df.loc[df["trap_flag"], "event_type"] = "trap"
    df.loc[df["absorption_flag"], "event_type"] = "absorption"
    # spoof — фоновый контекст, не перетирает торговые паттерны
    df["spoof_context"] = df["spoof_activity"] > 0

    return df.reset_index()

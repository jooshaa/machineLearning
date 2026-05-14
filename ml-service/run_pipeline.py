import asyncio
import pandas as pd
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest


def main():
    print("🚀 Starting CONTEXT-AWARE L3 Order Flow Engine...")

    symbol = "NQ.FUT"
    start = "2023-01-05T14:30:00"
    end = "2023-01-05T15:30:00"

    # 1. Fetch MBO Data
    print(f"📥 Fetching Databento Level 3 MBO data for {symbol}...")
    try:
        mbo_df = fetch_mbo_data(symbol, start, end)
        if mbo_df.empty:
            print("❌ No data returned.")
            return
        print(f"✅ Fetched {len(mbo_df)} MBO events.")
    except Exception as e:
        print(f"❌ Fetch failed: {e}")
        return

    # 2. Build L3 Order Book
    print("🧱 Reconstructing Order Book State...")
    events = process_mbo_stream(mbo_df)
    events_df = pd.DataFrame(events)

    # 3. Enrich Pipeline
    print("🧠 Running Intelligence Layer...")
    # Step A: Base Features
    features = extract_l3_features(mbo_df, events_df)
    # Step B: Context
    features = compute_context(features)
    # Step C: Sequence
    features = compute_sequence(features)
    # Step D: Scoring
    features = score_events(features)
    # Step E: Decision
    features = apply_decision_rules(features)

    print(f"✅ Extracted enriched features for {len(features)} events.")

    # 4. Run Backtest
    print("📈 Running Decision-based Backtest Engine...")
    result = run_l3_backtest(features)

    f = result.get('funnel', {})
    res = result
    tot = f.get('total_events', 1)
    p_bias = f.get('passed_bias', 0)
    b_bias = f.get('blocked_bias', 0)
    p_bound = f.get('passed_boundary', 0)
    b_bound = f.get('blocked_boundary', 0)
    b_lvn = f.get('blocked_lvn', 0)
    p_lvn = f.get('passed_lvn', 0)
    b_agg = f.get('blocked_aggression', 0)
    p_agg = f.get('passed_aggression', 0)
    b_poc = f.get('blocked_internal_poc', 0)
    b_cool = f.get('blocked_cooldown', 0)
    b_lvl = f.get('blocked_traded_level', 0)
    b_rr = f.get('blocked_rr_too_low', 0)
    
    print("\n\n1. Результаты валидации фильтров (На примере Периода 1):")
    print(f"Фильтр 1 — Daily/Session Bias: прошло {p_bias} / заблокировано {b_bias} ({(b_bias/tot*100):.1f}%)")
    print(f"Фильтр 2 — VAH/VAL Boundary:   прошло {p_bound} / заблокировано {b_bound} ({(b_bound/max(1, p_bias)*100):.1f}%)")
    print(f"Фильтр 3 — Cooldown:           заблокировано {b_cool}")
    print(f"Фильтр 4 — Traded Level:       заблокировано {b_lvl}")
    print(f"Фильтр 5 — LVN:                прошло {p_lvn} / заблокировано {b_lvn} ({(b_lvn/max(1, p_bound)*100):.1f}%)")
    print(f"Фильтр 6 — Aggression:         прошло {p_agg} / заблокировано {b_agg} ({(b_agg/max(1, p_lvn)*100):.1f}%)")
    print(f"Фильтр 7 — Internal POC:       прошло {res['stats']['total_trades'] + b_rr} / заблокировано {b_poc} ({(b_poc/max(1, p_agg)*100):.1f}%)")
    print(f"Фильтр 8 — Min R:R (<2.5):     заблокировано {b_rr}")
    print(f"Итого сделок:                  {res['stats']['total_trades']} сделок за период")

    print("\n===============================")
    print("📊 CONTEXT-AWARE L3 RESULTS")
    print("===============================")
    print(f"Total Trades : {result['stats']['total_trades']}")
    print(f"Win Rate     : {result['stats']['win_rate']:.2f}%")
    print(f"Avg R:R      : {result['stats'].get('avg_R', 0):.2f}")
    
    if result["trades"]:
        print("\nTop 3 High-Conviction Trades:")
        top_trades = sorted([t for t in result["trades"] if t["result"] == "win"], key=lambda x: x["score"], reverse=True)[:3]
        for t in top_trades:
            print(
                f"[{t.get('result', 'open').upper()}] {t['direction'].upper()} @ {t.get('entry_price', 0):.2f} | Score: {t.get('score', 0):.2f} | Pattern: {t.get('event_type', 'none')} | Loc: {t.get('location', 'none')}"
            )
            
        # --- EXPORT TO ML DATASET ---
        ml_data = []
        for t in result["trades"]:
            if t["result"] not in ["win", "loss"]: continue
            
            row_data = {
                "timestamp_utc": t["ts"],
                "direction": t["direction"],
                "result": t["result"],
                "outcome_r": t["outcome_R"],
                "target_is_good_setup": 1 if t["result"] == "win" else 0,
            }
            if "features" in t and isinstance(t["features"], dict):
                for k, v in t["features"].items():
                    if k not in ["ts", "price", "symbol", "index", "action", "order_id"]:
                        row_data[k] = v
            ml_data.append(row_data)
            
        if ml_data:
            import os
            os.makedirs("orderflow_ml", exist_ok=True)
            df_ml = pd.DataFrame(ml_data)
            out_path = "orderflow_ml/ml_dataset.csv"
            df_ml.to_csv(out_path, index=False)
            print(f"\n💾 Saved {len(df_ml)} real L3 trades to ML Dataset: {out_path}")

if __name__ == "__main__":
    main()

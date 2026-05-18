from __future__ import annotations

from typing import Literal
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split

from app.backtester import (
    AdvancedBacktestRequest,
    FetchCandlesRequest,
    fetch_candles,
    run_advanced_backtest,
)
from app.fabio_engine import FabioBacktestRequest, run_fabio_backtest

# Databento & Order Flow Engine imports
from app.data.databento_client import fetch_mbo_data
from app.engine.orderbook import process_mbo_stream
from app.engine.features import extract_l3_features
from app.engine.context import compute_context
from app.engine.sequence import compute_sequence
from app.engine.scoring import score_events
from app.engine.decision import apply_decision_rules
from app.engine.orderflow_backtester import run_l3_backtest, save_trades_to_history
from app.engine.analysis import analyze_trade_history
from app.engine.jobs import job_manager
from fastapi import BackgroundTasks
import time
from app.engine.orderflow_backtester import run_l3_backtest
import strategy_volume_delta


app = FastAPI(title="Trading Journal ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TradeRecord(BaseModel):
    id: str | None = None
    pair: str
    strategyVersion: str = "v1"
    timeframe: str | None = None
    session: Literal["London", "NY", "Asia"]
    setup: Literal["breakout", "pullback", "reversal"]
    direction: Literal["buy", "sell"]
    entryPrice: float
    stopLoss: float
    takeProfit: float
    riskReward: float
    result: Literal["win", "loss"]
    confidence: int = 3
    confluence: int = 1
    emotion: str | None = None
    mistake: str | None = None
    notes: str | None = None
    screenshotUrls: list[str] | None = None
    screenshotAnalysisStatus: str = "none"
    screenshotSummary: str | None = None
    screenshotDetectedSetup: str | None = None
    screenshotQualityScore: int | None = None
    screenshotTags: list[str] | None = None
    profit: float
    createdAt: str | None = None


class PredictRequest(BaseModel):
    trades: list[TradeRecord]
    trade: TradeRecord | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(request: PredictRequest):
    if len(request.trades) < 5:
        raise HTTPException(status_code=400, detail="At least 5 trades are required.")

    dataframe = normalize_dataframe(request.trades)

    if dataframe["result"].nunique() < 2:
        raise HTTPException(
            status_code=400,
            detail="The dataset must contain both wins and losses.",
        )

    features = dataframe[FEATURE_COLUMNS]
    target = (dataframe["result"] == "win").astype(int)
    pipeline = build_pipeline()
    pipeline.fit(features, target)
    evaluation = evaluate_model(dataframe)

    trade_to_score = (
        normalize_dataframe([request.trade]) if request.trade else dataframe.tail(1)
    )
    scored_features = trade_to_score[FEATURE_COLUMNS]
    win_probability = float(pipeline.predict_proba(scored_features)[0][1])

    feature_importances = extract_feature_importances(pipeline)

    return {
        "win_probability": round(win_probability * 100, 2),
        "risk_score": round((1 - win_probability) * 100, 2),
        "insights": build_insights(dataframe),
        "feature_importance": feature_importances[:5],
        "best_setup": build_best_setup(dataframe),
        "worst_session": build_worst_session(dataframe),
        "evaluation": evaluation,
        "sample_size": int(len(dataframe)),
    }


FEATURE_COLUMNS = [
    "pair",
    "strategyVersion",
    "timeframe",
    "session",
    "setup",
    "direction",
    "entryPrice",
    "stopLoss",
    "takeProfit",
    "riskReward",
    "confidence",
    "confluence",
    "emotion",
    "screenshotDetectedSetup",
    "screenshotQualityScore",
]

NUMERIC_COLUMNS = [
    "entryPrice",
    "stopLoss",
    "takeProfit",
    "riskReward",
    "confidence",
    "confluence",
    "screenshotQualityScore",
]
CATEGORICAL_COLUMNS = [
    "pair",
    "strategyVersion",
    "timeframe",
    "session",
    "setup",
    "direction",
    "emotion",
    "screenshotDetectedSetup",
]


def normalize_dataframe(trades: list[TradeRecord | None]) -> pd.DataFrame:
    rows = []
    for trade in trades:
        if trade is None:
            continue
        payload = trade.model_dump(by_alias=False)
        rows.append(payload)

    dataframe = pd.DataFrame(rows)

    if dataframe.empty:
        return dataframe

    if "createdAt" in dataframe.columns:
        dataframe["createdAt"] = pd.to_datetime(dataframe["createdAt"], errors="coerce")

    return dataframe


def evaluate_model(dataframe: pd.DataFrame) -> dict:
    if len(dataframe) < 8 or dataframe["result"].nunique() < 2:
        return {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "roc_auc": None,
            "holdout_size": 0,
        }

    ordered = dataframe.sort_values("createdAt", na_position="last").reset_index(drop=True)
    split_index = max(int(len(ordered) * 0.7), 1)
    x_train = ordered.iloc[:split_index][FEATURE_COLUMNS]
    x_test = ordered.iloc[split_index:][FEATURE_COLUMNS]
    y_train = (ordered.iloc[:split_index]["result"] == "win").astype(int)
    y_test = (ordered.iloc[split_index:]["result"] == "win").astype(int)

    if len(x_test) == 0 or y_train.nunique() < 2 or y_test.nunique() < 2:
        return {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "roc_auc": None,
            "holdout_size": 0,
            "split_type": "chronological",
            "train_end_date": None,
            "test_start_date": None,
        }

    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    probabilities = pipeline.predict_proba(x_test)[:, 1]

    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 3),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 3),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 3),
        "holdout_size": int(len(x_test)),
        "split_type": "chronological",
        "train_end_date": serialize_timestamp(ordered.iloc[split_index - 1]["createdAt"]),
        "test_start_date": serialize_timestamp(ordered.iloc[split_index]["createdAt"]),
    }


def build_pipeline() -> Pipeline:
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", categorical_pipeline, CATEGORICAL_COLUMNS),
            ("numeric", numeric_pipeline, NUMERIC_COLUMNS),
        ]
    )

    classifier = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def extract_feature_importances(pipeline: Pipeline) -> list[dict]:
    preprocessor: ColumnTransformer = pipeline.named_steps["preprocessor"]
    classifier: RandomForestClassifier = pipeline.named_steps["classifier"]
    encoded_feature_names = preprocessor.get_feature_names_out()
    importances = classifier.feature_importances_

    ranked = sorted(
        zip(encoded_feature_names, importances),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        {"feature": feature, "importance": round(float(importance), 4)}
        for feature, importance in ranked
        if importance > 0
    ]


def build_insights(dataframe: pd.DataFrame) -> list[str]:
    insights: list[str] = []

    session_stats = dataframe.groupby("session")["result"].apply(
        lambda values: (values == "win").mean()
    )
    if not session_stats.empty:
        best_session = session_stats.idxmax()
        worst_session = session_stats.idxmin()
        insights.append(
            f"You perform better in {best_session} session ({session_stats.max() * 100:.0f}% win rate)."
        )
        if best_session != worst_session:
            insights.append(
                f"{worst_session} session is currently your weakest context ({session_stats.min() * 100:.0f}% win rate)."
            )

    setup_stats = dataframe.groupby("setup")["result"].apply(
        lambda values: (values == "win").mean()
    )
    if not setup_stats.empty:
        insights.append(
            f"{setup_stats.idxmax().capitalize()} strategy has the highest win rate."
        )

    low_rr = dataframe[dataframe["riskReward"] < 1.5]
    if not low_rr.empty:
        low_rr_profit = low_rr["profit"].sum()
        if low_rr_profit <= 0:
            insights.append("RR below 1.5 is currently unprofitable in your journal.")

    average_profit_by_pair = dataframe.groupby("pair")["profit"].mean()
    if not average_profit_by_pair.empty:
        strongest_pair = average_profit_by_pair.idxmax()
        insights.append(
            f"{strongest_pair} produces your strongest average profit per trade."
        )

    emotion_stats = dataframe.dropna(subset=["emotion"]).groupby("emotion")["result"].apply(
        lambda values: (values == "win").mean()
    )
    if not emotion_stats.empty and len(emotion_stats) > 1:
        insights.append(
            f"{emotion_stats.idxmax().capitalize()} trades perform best, while {emotion_stats.idxmin()} trades drag results down."
        )

    screenshot_stats = dataframe.dropna(subset=["screenshotDetectedSetup"]).groupby(
        "screenshotDetectedSetup"
    )["result"].apply(lambda values: (values == "win").mean())
    if not screenshot_stats.empty:
        insights.append(
            f"Charts labeled as {screenshot_stats.idxmax()} visually perform best in your screenshot-reviewed sample."
        )

    return insights[:4]


def build_best_setup(dataframe: pd.DataFrame) -> str | None:
    setup_stats = dataframe.groupby("setup")["result"].apply(
        lambda values: (values == "win").mean()
    )
    if setup_stats.empty:
        return None
    return str(setup_stats.idxmax())


def build_worst_session(dataframe: pd.DataFrame) -> str | None:
    session_stats = dataframe.groupby("session")["result"].apply(
        lambda values: (values == "win").mean()
    )
    if session_stats.empty:
        return None
    return str(session_stats.idxmin())


def serialize_timestamp(value) -> str | None:
    if pd.isna(value):
        return None
    return str(pd.Timestamp(value).isoformat())


# ---------------------------------------------------------------------------
# Advanced backtesting endpoints
# ---------------------------------------------------------------------------


@app.post("/fetch-candles")
def api_fetch_candles(request: FetchCandlesRequest):
    try:
        candles = fetch_candles(request)
        if not candles:
            raise HTTPException(status_code=404, detail="No data found for the given symbol/period.")
        return {"candles": candles, "count": len(candles)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch candles: {str(exc)}")


@app.post("/backtest-advanced")
def api_backtest_advanced(request: AdvancedBacktestRequest):
    if len(request.candles) < 50:
        raise HTTPException(status_code=400, detail="At least 50 candles are required for backtesting.")
    if not request.entry_conditions:
        raise HTTPException(status_code=400, detail="At least one entry condition is required.")
    try:
        result = run_advanced_backtest(request)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(exc)}")

# ---------------------------------------------------------------------------
# Fabio AI — Persistent Model & Memory
# ---------------------------------------------------------------------------
import json
import os
import joblib
from datetime import datetime

FABIO_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FABIO_MODEL_PATH = os.path.join(FABIO_DATA_DIR, "fabio_model.joblib")
FABIO_MEMORY_PATH = os.path.join(FABIO_DATA_DIR, "fabio_memory.json")

os.makedirs(FABIO_DATA_DIR, exist_ok=True)

def _load_fabio_model():
    """Load trained model from disk if it exists."""
    if os.path.exists(FABIO_MODEL_PATH):
        try:
            return joblib.load(FABIO_MODEL_PATH)
        except Exception:
            return None
    return None

def _load_fabio_memory() -> dict:
    """Load accumulated AI memory from disk."""
    if os.path.exists(FABIO_MEMORY_PATH):
        try:
            with open(FABIO_MEMORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sessions": [], "cumulative_insights": [], "total_trades_analyzed": 0}

def _save_fabio_memory(memory: dict):
    """Save AI memory to disk."""
    with open(FABIO_MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2, default=str)

# Load model on startup
fabio_model = _load_fabio_model()

class TrainFabioRequest(BaseModel):
    trades: list[dict]

@app.post("/train-fabio")
def api_train_fabio(request: TrainFabioRequest):
    if len(request.trades) < 10:
        raise HTTPException(status_code=400, detail="Need at least 10 trades to train the model.")

    try:
        trades_raw = request.trades
        total = len(trades_raw)

        # ── 1. Pattern Analysis ──
        setup_stats: dict[str, dict] = {}
        session_stats: dict[str, dict] = {}
        hour_stats: dict[int, dict] = {}

        for t in trades_raw:
            setup = t.get("setup", "unknown")
            sess = t.get("features", {}).get("session", "all") if t.get("features") else "all"
            hour = t.get("features", {}).get("hour", -1) if t.get("features") else -1
            is_win = t.get("result") == "win"
            pnl = float(t.get("pnl_r", 0))

            if setup not in setup_stats:
                setup_stats[setup] = {"wins": 0, "total": 0, "pnl_r": 0.0}
            setup_stats[setup]["total"] += 1
            setup_stats[setup]["pnl_r"] += pnl
            if is_win:
                setup_stats[setup]["wins"] += 1

            if sess not in session_stats:
                session_stats[sess] = {"wins": 0, "total": 0, "pnl_r": 0.0}
            session_stats[sess]["total"] += 1
            session_stats[sess]["pnl_r"] += pnl
            if is_win:
                session_stats[sess]["wins"] += 1

            if hour >= 0:
                if hour not in hour_stats:
                    hour_stats[hour] = {"wins": 0, "total": 0, "pnl_r": 0.0}
                hour_stats[hour]["total"] += 1
                hour_stats[hour]["pnl_r"] += pnl
                if is_win:
                    hour_stats[hour]["wins"] += 1

        # Format breakdowns
        setup_breakdown = []
        for name, s in sorted(setup_stats.items(), key=lambda x: x[1]["pnl_r"], reverse=True):
            wr = round(s["wins"] / s["total"] * 100, 1) if s["total"] > 0 else 0
            setup_breakdown.append({
                "setup": name, "trades": s["total"], "win_rate": wr,
                "total_r": round(s["pnl_r"], 2),
                "grade": "A" if wr >= 60 and s["pnl_r"] > 0 else ("B" if wr >= 50 else ("C" if wr >= 40 else "F")),
            })

        session_breakdown = []
        for name, s in sorted(session_stats.items(), key=lambda x: x[1]["pnl_r"], reverse=True):
            wr = round(s["wins"] / s["total"] * 100, 1) if s["total"] > 0 else 0
            session_breakdown.append({
                "session": name, "trades": s["total"], "win_rate": wr,
                "total_r": round(s["pnl_r"], 2),
            })

        hour_breakdown = []
        for h, s in sorted(hour_stats.items()):
            wr = round(s["wins"] / s["total"] * 100, 1) if s["total"] > 0 else 0
            hour_breakdown.append({
                "hour": h, "trades": s["total"], "win_rate": wr,
                "total_r": round(s["pnl_r"], 2),
            })

        # ── 2. ML Model Training ──
        data = []
        for t in trades_raw:
            if not t.get("features"):
                continue
            # Keep all features to allow categoricals (like session)
            feats = t["features"].copy()
            feats["target"] = 1 if t["result"] == "win" else 0
            data.append(feats)

        metrics = {"accuracy": 0.0, "precision": 0.0, "samples": total}
        feature_importance = []

        if len(data) >= 10:
            df = pd.DataFrame(data)
            X = df.drop(columns=["target"])
            y = df["target"]

            # Define transformers for numeric and categorical columns
            numeric_cols = X.select_dtypes(include=['int64', 'float64', 'bool']).columns
            categorical_cols = X.select_dtypes(include=['object', 'string']).columns

            preprocessor = ColumnTransformer(
                transformers=[
                    ("num", Pipeline([
                        ("imputer", SimpleImputer(strategy="mean")),
                        ("scaler", StandardScaler())
                    ]), numeric_cols),
                    ("cat", Pipeline([
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
                    ]), categorical_cols)
                ]
            )

            pipeline = Pipeline([
                ("preprocessor", preprocessor),
                ("classifier", RandomForestClassifier(
                    n_estimators=200, max_depth=6, min_samples_leaf=2, random_state=42
                ))
            ])

            if y.nunique() >= 2 and len(X) >= 10:
                test_size = min(0.3, max(0.15, 3 / len(X)))
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42
                )
                pipeline.fit(X_train, y_train)
                y_pred = pipeline.predict(X_test)

                metrics["accuracy"] = round(float(accuracy_score(y_test, y_pred)), 3)
                metrics["precision"] = round(float(precision_score(y_test, y_pred, zero_division=0)), 3)

                importances = pipeline.named_steps["classifier"].feature_importances_
                
                # Get feature names after preprocessing
                feature_names = []
                if len(numeric_cols) > 0:
                    feature_names.extend(numeric_cols)
                if len(categorical_cols) > 0:
                    encoder = pipeline.named_steps["preprocessor"].named_transformers_["cat"].named_steps["encoder"]
                    cat_names = encoder.get_feature_names_out(categorical_cols)
                    feature_names.extend(cat_names)
                    
                for fname, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
                    if imp > 0.01:
                        feature_importance.append({
                            "feature": str(fname), "importance": round(float(imp), 4)
                        })

                # Save model to disk (persistent!)
                global fabio_model
                fabio_model = pipeline
                joblib.dump(pipeline, FABIO_MODEL_PATH)
            else:
                pipeline.fit(X, y)
                fabio_model = pipeline
                joblib.dump(pipeline, FABIO_MODEL_PATH)

        # ── 3. Generate Insights ──
        insights = []
        recommendations = []

        if setup_breakdown:
            best = setup_breakdown[0]
            worst = setup_breakdown[-1]
            insights.append(f"🏆 Best setup: {best['setup']} ({best['win_rate']}% WR, {best['total_r']:+.1f}R)")
            if best["win_rate"] >= 55:
                recommendations.append(f"✅ Focus on {best['setup']} — it has a strong edge ({best['win_rate']}% WR)")
            if len(setup_breakdown) > 1 and worst["total_r"] < 0:
                insights.append(f"⚠️ Worst setup: {worst['setup']} ({worst['win_rate']}% WR, {worst['total_r']:+.1f}R)")
                recommendations.append(f"🚫 Consider disabling {worst['setup']} — it's losing money ({worst['total_r']:+.1f}R)")

        if session_breakdown:
            best_sess = session_breakdown[0]
            insights.append(f"📍 Best session: {best_sess['session']} ({best_sess['win_rate']}% WR, {best_sess['total_r']:+.1f}R)")
            if len(session_breakdown) > 1:
                worst_sess = session_breakdown[-1]
                if worst_sess["total_r"] < 0:
                    recommendations.append(f"📍 Trade only in {best_sess['session']} session — {worst_sess['session']} is unprofitable")

        if hour_breakdown:
            profitable_hours = [h for h in hour_breakdown if h["total_r"] > 0 and h["trades"] >= 2]
            losing_hours = [h for h in hour_breakdown if h["total_r"] < 0 and h["trades"] >= 2]
            if profitable_hours:
                best_h = max(profitable_hours, key=lambda x: x["total_r"])
                insights.append(f"⏰ Best hour: {best_h['hour']}:00 UTC ({best_h['win_rate']}% WR, {best_h['total_r']:+.1f}R)")
            if losing_hours:
                worst_h = min(losing_hours, key=lambda x: x["total_r"])
                insights.append(f"🚫 Avoid hour: {worst_h['hour']}:00 UTC ({worst_h['win_rate']}% WR, {worst_h['total_r']:+.1f}R)")
                recommendations.append(f"⏰ Avoid trading at {worst_h['hour']}:00 UTC — consistently loses money")

        if feature_importance:
            top = feature_importance[0]
            insights.append(f"🧠 Top ML signal: {top['feature']} (importance: {top['importance']:.0%})")

        # ── 3b. Context-Aware Advanced Insights ──
        # Group by location + setup + trend to find specific "danger zones"
        df_full = pd.DataFrame(data)
        if not df_full.empty and 'location' in df_full.columns and 'trend' in df_full.columns:
            danger_zones = df_full.groupby(['setup', 'location', 'trend'])['target'].agg(['mean', 'count'])
            danger_zones = danger_zones[danger_zones['count'] >= 2]
            for (setup, loc, trend), row in danger_zones.iterrows():
                if row['mean'] < 0.4: # Win rate < 40%
                    recommendations.append(f"🚫 Avoid {setup} at {loc} during {trend} trend — very low win rate ({row['mean']*100:.0f}%)")
                elif row['mean'] > 0.6: # Win rate > 60%
                    recommendations.append(f"✅ High conviction: {setup} at {loc} during {trend} trend ({row['mean']*100:.0f}% WR)")

        # Overall recommendation
        total_wr = round(len([t for t in trades_raw if t.get("result") == "win"]) / total * 100, 1) if total > 0 else 0
        total_pnl = round(sum(float(t.get("pnl_r", 0)) for t in trades_raw), 2)
        if total_wr >= 55 and total_pnl > 0:
            recommendations.append(f"✅ Strategy is profitable ({total_wr}% WR, {total_pnl:+.1f}R). Keep current parameters.")
        elif total_pnl > 0:
            recommendations.append(f"⚠️ Profitable ({total_pnl:+.1f}R) but low WR ({total_wr}%). Tighten entry filters.")
        else:
            recommendations.append(f"❌ Strategy is losing ({total_pnl:+.1f}R). Review parameters or switch to profitable setups only.")

        # ── 4. Save to persistent memory ──
        memory = _load_fabio_memory()

        session_record = {
            "timestamp": datetime.now().isoformat(),
            "total_trades": total,
            "win_rate": total_wr,
            "total_pnl_r": total_pnl,
            "accuracy": metrics["accuracy"],
            "setup_breakdown": setup_breakdown,
            "session_breakdown": session_breakdown,
            "insights": insights,
            "recommendations": recommendations,
        }
        memory["sessions"].append(session_record)
        memory["total_trades_analyzed"] = memory.get("total_trades_analyzed", 0) + total

        # Merge recommendations across sessions (keep unique, latest wins)
        all_recs = set()
        for s in memory["sessions"][-5:]:  # last 5 sessions
            for r in s.get("recommendations", []):
                all_recs.add(r)
        memory["cumulative_insights"] = list(all_recs)

        _save_fabio_memory(memory)

        return {
            "status": "success",
            "metrics": metrics,
            "setup_breakdown": setup_breakdown,
            "session_breakdown": session_breakdown,
            "hour_breakdown": hour_breakdown,
            "feature_importance": feature_importance[:8],
            "insights": insights,
            "recommendations": recommendations,
            "memory": {
                "total_sessions": len(memory["sessions"]),
                "total_trades_analyzed": memory["total_trades_analyzed"],
                "model_saved": os.path.exists(FABIO_MODEL_PATH),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(exc)}")


@app.get("/fabio-ai-memory")
def api_fabio_ai_memory():
    """Return all accumulated AI learnings and recommendations."""
    memory = _load_fabio_memory()
    has_model = os.path.exists(FABIO_MODEL_PATH)

    # Aggregate best setups across all sessions
    all_setups: dict[str, dict] = {}
    for s in memory.get("sessions", []):
        for sb in s.get("setup_breakdown", []):
            name = sb["setup"]
            if name not in all_setups:
                all_setups[name] = {"wins": 0, "total": 0, "pnl_r": 0.0}
            all_setups[name]["total"] += sb["trades"]
            all_setups[name]["wins"] += round(sb["trades"] * sb["win_rate"] / 100)
            all_setups[name]["pnl_r"] += sb["total_r"]

    lifetime_setups = []
    for name, s in sorted(all_setups.items(), key=lambda x: x[1]["pnl_r"], reverse=True):
        wr = round(s["wins"] / s["total"] * 100, 1) if s["total"] > 0 else 0
        lifetime_setups.append({
            "setup": name, "total_trades": s["total"], "win_rate": wr,
            "total_r": round(s["pnl_r"], 2),
        })

    return {
        "has_model": has_model,
        "total_sessions": len(memory.get("sessions", [])),
        "total_trades_analyzed": memory.get("total_trades_analyzed", 0),
        "cumulative_recommendations": memory.get("cumulative_insights", []),
        "lifetime_setup_performance": lifetime_setups,
        "recent_sessions": memory.get("sessions", [])[-5:],
    }


@app.post("/backtest-fabio")
def api_backtest_fabio(request: FabioBacktestRequest):
    if len(request.candles) < 80:
        raise HTTPException(status_code=400, detail="At least 80 candles needed for Volume Profile.")
    try:
        result = run_fabio_backtest(request, trained_model=fabio_model)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fabio backtest failed: {str(exc)}")

@app.post("/backtest-volume-delta")
async def backtest_volume_delta():
    try:
        result_df = strategy_volume_delta.main()
        
        if result_df.empty:
            return {"signals": [], "summary": {"total": 0}}
            
        signals = result_df.to_dict(orient='records')
        
        summary = {
            "total": len(result_df),
            "wins": len(result_df[result_df['outcome'] == 'win']),
            "losses": len(result_df[result_df['outcome'] == 'loss']),
            "timeouts": len(result_df[result_df['outcome'] == 'timeout']),
            "avg_r": float(result_df['r_multiple'].mean()) if not result_df.empty else 0.0,
        }
        
        return {"signals": signals, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Volume Delta Backtest failed: {str(e)}")

@app.get("/candles/{date}")
async def get_candles(
    date: str,
    timeframe: str = "5min",
    days_before: int = 3,
    days_after: int = 1,
):
    """
    Load MBO parquet files for date ± days_before/days_after, build OHLC candles.
    date: YYYY-MM-DD (the entry/signal date)
    timeframe: 1m | 5m | 15m | 1H (default 5min)
    days_before: how many prior calendar days to include (default 3)
    days_after:  how many subsequent calendar days to include (default 1)
    """
    from datetime import date as dt_date, timedelta

    timeframe_map = {
        "1m":   "1min",
        "1min": "1min",
        "5m":   "5min",
        "5min": "5min",
        "15m":  "15min",
        "15min":"15min",
        "1H":   "1h",
        "1h":   "1h",
    }
    resample_rule = timeframe_map.get(timeframe, "5min")

    base_date = dt_date.fromisoformat(date)
    data_dir = "data/raw/mbo/NQ"

    # Collect all available parquet files in the requested range
    frames = []
    for delta in range(-days_before, days_after + 1):
        d = base_date + timedelta(days=delta)
        path = os.path.join(data_dir, f"{d}.parquet")
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_parquet(path)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        raise HTTPException(status_code=404, detail=f"No parquet data found around date {date}")

    try:
        mbo_df = pd.concat(frames)

        # Filter for trades only
        trades = mbo_df[mbo_df['action'] == 'T'].copy()
        if trades.empty:
            return []

        # Handle price scale
        median_price = trades['price'].median()
        if median_price > 1e8:
            trades['price'] = trades['price'] / 1e9
        elif median_price > 1e5:
            trades['price'] = trades['price'] / 1e4

        # Filter outliers
        q01 = trades['price'].quantile(0.001)
        q999 = trades['price'].quantile(0.999)
        trades = trades[(trades['price'] >= q01) & (trades['price'] <= q999)]

        # Ensure datetime index
        if not isinstance(trades.index, pd.DatetimeIndex):
            trades.index = pd.to_datetime(trades.index)

        trades = trades.sort_index()

        # Resample to requested timeframe
        candles = trades['price'].resample(resample_rule).ohlc()
        candles.dropna(inplace=True)

        result = []
        for ts, row in candles.iterrows():
            result.append({
                "timestamp": ts.isoformat(),
                "open":  float(row['open']),
                "high":  float(row['high']),
                "low":   float(row['low']),
                "close": float(row['close']),
            })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build candles: {str(e)}")

# ---------------------------------------------------------------------------
# Level 3 (MBO) Order Flow Data Pipeline Endpoints
# ---------------------------------------------------------------------------

@app.get("/databento/fetch")
def api_databento_fetch(symbol: str = "NQ", start: str = "2023-01-01T00:00:00", end: str = "2023-01-02T00:00:00"):
    try:
        df = fetch_mbo_data(symbol, start, end)
        if df.empty:
            raise HTTPException(status_code=404, detail="No MBO data found")
        df.to_parquet(f"data/{symbol}_mbo.parquet")
        return {"status": "success", "rows": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orderbook/build")
def api_orderbook_build(symbol: str = "NQ"):
    try:
        mbo_df = pd.read_parquet(f"data/{symbol}_mbo.parquet")
        
        # 2. Process MBO into Events
        print(f"📊 Raw MBO data loaded: {len(mbo_df)} rows")
        if not mbo_df.empty:
            print(f"⏰ Data time range: {mbo_df.index[0]} to {mbo_df.index[-1]}")
            print(f"🧪 Unique actions in data: {mbo_df['action'].unique()}")
            
        events = process_mbo_stream(mbo_df)
        print(f"✅ Generated {len(events)} trade events from MBO stream")
        
        events_df = pd.DataFrame(events)
        if events_df.empty:
            return {"status": "success", "events": 0}
            
        events_df.to_parquet(f"data/{symbol}_l3_events.parquet")
        return {"status": "success", "events": len(events_df)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fetch MBO data first")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/features/extract")
def api_features_extract(symbol: str = "NQ"):
    try:
        mbo_df = pd.read_parquet(f"data/{symbol}_mbo.parquet")
        events_df = pd.read_parquet(f"data/{symbol}_l3_events.parquet")
        
        # Build raw features
        features = extract_l3_features(mbo_df, events_df)
        
        # 1. Add Context (VAH, VAL, Trend, Session)
        features = compute_context(features)
        
        # 2. Add Event Sequence (event_t-3 -> ...)
        features = compute_sequence(features)
        
        # 3. Add Event Score
        features = score_events(features)
        
        # 4. Filter via Decision Rules
        features = apply_decision_rules(features)
        
        features.to_json(f"data/{symbol}_l3_features.json", orient="records", date_format="iso")
        return {"status": "success", "features_events": len(features)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Build orderbook events first")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Async Level 3 (MBO) Pipeline
# ---------------------------------------------------------------------------

class L3BacktestRequest(BaseModel):
    symbol: str = "NQ.FUT"
    start: str = "2023-01-05T14:30:00"
    end: str = "2023-01-05T15:30:00"
    compare_ohlcv: bool = False
    discovery_mode: bool = False 
    use_validated_edge: bool = True # New: Only trade statistically robust segments

def run_l3_pipeline_async(job_id: str, symbol: str, start: str, end: str, discovery_mode: bool = False, use_validated_edge: bool = True):
    try:
        # Step 1: Fetch
        job_manager.update_job(job_id, 0.1, "fetching_data")
        mbo_df = fetch_mbo_data(symbol, start, end)
        if mbo_df.empty:
            raise Exception(f"No MBO data found for {symbol} on {start}. Databento might not have data for this specific time range.")
        
        # --- FIX: Symbol Normalization ---
        # Databento might return NQH3 for symbol NQ.FUT. 
        # Since we already filtered by symbol in fetch_mbo_data, 
        # we don't need to strictly filter it again unless there are multiple symbols.
        if 'symbol' in mbo_df.columns:
            mbo_df['symbol'] = symbol.split('.')[0] # Normalize to "NQ"
            
        if job_manager.is_cancelled(job_id): return

        # Step 2: Build Orderbook
        job_manager.update_job(job_id, 0.4, "building_orderbook")
        events = process_mbo_stream(mbo_df)
        events_df = pd.DataFrame(events)
        if job_manager.is_cancelled(job_id): return

        # Step 3: Detecting Events (Features)
        job_manager.update_job(job_id, 0.7, "detecting_events")
        # Ensure symbols match for feature extraction
        if not events_df.empty:
            events_df['symbol'] = symbol.split('.')[0]
            
        features = extract_l3_features(mbo_df, events_df)
        
        # Step 4: Run OrderFlow Backtest
        job_manager.update_job(job_id, 0.9, "simulating_trades")
        from app.engine.orderflow_backtester import run_l3_backtest
        result = run_l3_backtest(
            features, 
            filter_signals=not discovery_mode,
            use_validated_edge=use_validated_edge
        )
        
        # FIX: Ensure result is JSON serializable (no numpy types)
        def clean_types(obj):
            if isinstance(obj, dict):
                return {k: clean_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_types(i) for i in obj]
            elif hasattr(obj, 'item'): # Handle numpy types
                return obj.item()
            return obj

        clean_result = clean_types(result)
        save_trades_to_history(clean_result["trades"])
        
        job_manager.finish_job(job_id, {
            "stats": clean_result["stats"],
            "trades": clean_result["trades"],
            "features_count": len(features)
        })
    except Exception as e:
        job_manager.fail_job(job_id, str(e))

@app.post("/backtest-l3/start")
def api_backtest_l3_start(request: L3BacktestRequest, background_tasks: BackgroundTasks):
    # Validate range (Max 1 day)
    start_dt = datetime.fromisoformat(request.start.replace('Z', ''))
    end_dt = datetime.fromisoformat(request.end.replace('Z', ''))
    if (end_dt - start_dt).total_seconds() > 86400 * 1.1:
        raise HTTPException(status_code=400, detail="MBO range exceeds 1 day limit.")

    job_id = job_manager.create_job()
    background_tasks.add_task(
        run_l3_pipeline_async, 
        job_id, 
        request.symbol, 
        request.start, 
        request.end, 
        request.discovery_mode,
        request.use_validated_edge
    )
    return {"job_id": job_id}

@app.get("/backtest-l3/analysis")
def api_backtest_l3_analysis():
    """Returns the full statistical report of all logged trades."""
    report = analyze_trade_history()
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
        
    def clean_types(obj):
        if isinstance(obj, dict):
            return {k: clean_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_types(i) for i in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        return obj
        
    return clean_types(report)

@app.get("/backtest-l3/status/{job_id}")
def api_backtest_l3_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "progress": job["progress"],
        "stage": job["stage"],
        "error": job["error"]
    }

@app.get("/backtest-l3/result/{job_id}")
def api_backtest_l3_result(job_id: str):
    job = job_manager.get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done": raise HTTPException(status_code=400, detail="Job not finished")
    return job["result"]

@app.post("/backtest-l3/cancel/{job_id}")
def api_backtest_l3_cancel(job_id: str):
    job_manager.cancel_job(job_id)
    return {"status": "cancelled"}


@app.get("/candles/local/{date}")
async def get_local_candles(date: str, symbol: str = "NQ"):
    path = f"data/raw/mbo/{symbol}/{date}.parquet"
    if not os.path.exists(path):
        # Try without symbol subdir just in case
        path_alt = f"data/raw/mbo/{date}.parquet"
        if os.path.exists(path_alt):
            path = path_alt
        else:
            return {"candles": []}
    
    df = pd.read_parquet(path)
    
    # Берём только реальные сделки (action == 'T')
    if "action" in df.columns:
        df = df[df["action"] == "T"]
        
    ts_col = "ts_event" if "ts_event" in df.columns else "ts"
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    
    # Убираем outliers внутри каждого минутного бара
    df = df.set_index(ts_col).sort_index()
    df['minute'] = df.index.floor('1min')
    minute_median = df.groupby('minute')['price'].transform('median')
    minute_std = df.groupby('minute')['price'].transform('std').fillna(0)
    df = df[abs(df['price'] - minute_median) <= minute_std * 3]
    df = df.drop(columns=['minute'])
    df = df.reset_index()
    
    # Фильтр аномалий
    q01 = df["price"].quantile(0.001)
    q999 = df["price"].quantile(0.999)
    df = df[(df["price"] >= q01) & (df["price"] <= q999)]
    
    # Не фильтруем по времени — берём весь торговый день
    # NY сессия 14:30-21:00 UTC уже в файле
    
    # Агрегируем в 1-минутные свечи
    df = df.set_index(ts_col).sort_index()
    bars = df["price"].resample("1min").ohlc()
    bars["volume"] = df["size"].resample("1min").sum()
    bars = bars.dropna()
    
    candles = [
        {
            "timestamp": ts.isoformat(), 
            "open": float(r.open), 
            "high": float(r.high), 
            "low": float(r.low), 
            "close": float(r.close), 
            "volume": int(r.volume)
        }
        for ts, r in bars.iterrows()
    ]
    return {"candles": candles}

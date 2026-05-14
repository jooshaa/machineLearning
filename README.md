# AI Trading Journal

Monorepo for an AI-powered trading journal and analysis system with:

- `backend`: NestJS REST API with PostgreSQL
- `ml-service`: Python ML analysis service using Pandas and scikit-learn
- `frontend`: Next.js dashboard with Tailwind CSS

## Architecture

- Traders submit journal entries to the NestJS API.
- The API stores trades in PostgreSQL and computes account analytics.
- The AI analysis endpoint sends historical trades and the latest trade to the Python service.
- The Python service trains a simple, extendable classifier and returns win probability, feature importance, and journal insights.
- The backtest endpoint evaluates simple rule-based trade logic against uploaded candle data.
- The Next.js app displays trades, analytics, and AI summaries.

## Run locally

### 1. Start PostgreSQL

```bash
docker compose up -d
```

### 2. Start the backend

```bash
cd backend
npm install
cp .env.example .env
npm run start:dev
```

The backend runs on `http://localhost:3001`.

### 3. Start the ML service

```bash
cd ml-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The ML service runs on `http://localhost:8000`.

### 4. Start the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

The frontend runs on `http://localhost:3000`.

PostgreSQL is exposed on `http://localhost:5433` to avoid conflicts with a local Postgres instance already using port `5432`.

### Optional screenshot vision analysis

If you want AI to analyze uploaded chart screenshots, set `OPENAI_API_KEY` in [backend/.env](/Users/asal/Desktop/machine%20learning/backend/.env). The backend uses the OpenAI Responses API with image input to produce a screenshot summary, detected setup, quality score, and tags for each trade.

## API overview

- `POST /trades`
- `GET /trades`
- `POST /trades/import-csv`
- `POST /trades/:id/analyze-screenshots`
- `DELETE /trades/:id`
- `POST /strategies`
- `GET /strategies`
- `GET /analytics`
- `GET /ai-analysis`
- `POST /backtests` — simple rule-based backtest
- `POST /backtests/fetch-candles` — auto-fetch OHLCV from Yahoo Finance
- `POST /backtests/advanced` — indicator-based backtest with full analytics

## Advanced backtesting

The advanced backtester supports:

- **Auto data fetch**: Fetch OHLCV candles by symbol (EURUSD, BTCUSD, XAUUSD, etc.) and timeframe from Yahoo Finance.
- **20+ technical indicators**: SMA, EMA, RSI, ATR, MACD, Bollinger Bands, Stochastic, ADX.
- **Condition-based entries**: Define rules like "RSI below 30 AND price crosses above SMA 50".
- **ATR-based risk management**: Stop loss and take profit calculated from ATR multiples.
- **Comprehensive stats**: Win rate, profit factor, Sharpe ratio, Sortino ratio, max drawdown, streaks, monthly breakdown.

## CSV workflows

- Import trade-history CSV from the `Trades` page to bulk-train the journal model.
- Upload candle CSV from the `Backtests` page to test a strategy on historical OHLC data.
- Common candle headers: `timestamp`, `open`, `high`, `low`, `close`.
- Common trade headers: `pair` or `symbol`, `strategy_version`, `timeframe`, `session`, `setup`, `direction`, `entry_price`, `stop_loss`, `take_profit`, `risk_reward`, `profit`, `result`, `confidence`, `emotion`, `mistake`, `notes`, `screenshot_urls`.

## Notes

- The system does not generate buy or sell signals.
- The ML service is intentionally simple to keep it explainable and extendable.
- The advanced backtester uses Yahoo Finance data — not suitable for live trading decisions.
- TypeORM `synchronize` is enabled for local development. Use migrations before production deployment.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pair VARCHAR(20) NOT NULL,
  strategy_version VARCHAR(40) NOT NULL DEFAULT 'v1',
  timeframe VARCHAR(10),
  session VARCHAR(20) NOT NULL,
  setup VARCHAR(20) NOT NULL,
  direction VARCHAR(10) NOT NULL,
  entry_price NUMERIC(14, 6) NOT NULL,
  stop_loss NUMERIC(14, 6) NOT NULL,
  take_profit NUMERIC(14, 6) NOT NULL,
  risk_reward NUMERIC(10, 2) NOT NULL,
  result VARCHAR(10) NOT NULL,
  confidence INTEGER NOT NULL DEFAULT 3,
  confluence INTEGER NOT NULL DEFAULT 1,
  emotion VARCHAR(20),
  mistake VARCHAR(120),
  notes TEXT,
  screenshot_urls JSONB,
  screenshot_analysis_status VARCHAR(20) NOT NULL DEFAULT 'none',
  screenshot_summary TEXT,
  screenshot_detected_setup VARCHAR(40),
  screenshot_quality_score INTEGER,
  screenshot_tags JSONB,
  profit NUMERIC(12, 2) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(80) NOT NULL,
  version VARCHAR(40) NOT NULL,
  pair VARCHAR(20) NOT NULL,
  setup VARCHAR(20) NOT NULL,
  direction VARCHAR(10) NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  risk_reward NUMERIC(10, 2) NOT NULL DEFAULT 2,
  lookback INTEGER NOT NULL DEFAULT 20,
  forward_bars INTEGER NOT NULL DEFAULT 7,
  risk_percent NUMERIC(10, 4) NOT NULL DEFAULT 0.2,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  description TEXT,
  tags JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

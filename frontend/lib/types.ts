export interface Trade {
  id: string;
  pair: string;
  strategyVersion: string;
  timeframe: 'M5' | 'M15' | 'H1' | 'H4' | 'D1' | null;
  session: 'London' | 'NY' | 'Asia';
  setup: 'breakout' | 'pullback' | 'reversal';
  direction: 'buy' | 'sell';
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  result: 'win' | 'loss';
  confidence: number;
  confluence: number;
  emotion: 'calm' | 'confident' | 'hesitant' | 'fearful' | 'revenge' | 'neutral' | null;
  mistake: string | null;
  notes: string | null;
  screenshotUrls: string[];
  screenshotAnalysisStatus: 'none' | 'pending' | 'completed' | 'failed';
  screenshotSummary: string | null;
  screenshotDetectedSetup: string | null;
  screenshotQualityScore: number | null;
  screenshotTags: string[] | null;
  profit: number;
  createdAt: string;
}

export interface CreateTradePayload {
  pair: string;
  strategyVersion: string;
  timeframe: 'M5' | 'M15' | 'H1' | 'H4' | 'D1' | null;
  session: 'London' | 'NY' | 'Asia';
  setup: 'breakout' | 'pullback' | 'reversal';
  direction: 'buy' | 'sell';
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  result: 'win' | 'loss';
  confidence: number;
  confluence: number;
  emotion: 'calm' | 'confident' | 'hesitant' | 'fearful' | 'revenge' | 'neutral' | null;
  mistake: string | null;
  notes: string | null;
  screenshotUrls: string[];
  profit: number;
}

export interface AnalyticsSnapshot {
  totalTrades: number;
  winRate: number;
  averageRiskReward: number;
  profitFactor: number;
  drawdown: number;
  totalProfit: number;
  equityCurve: Array<{ index: number; equity: number }>;
  bestSetup: string | null;
  weakestSession: string | null;
  bestPair: string | null;
  averageConfidence: number;
  commonMistakes: Array<{ label: string; count: number }>;
}

export interface AiAnalysis {
  win_probability: number;
  risk_score: number;
  insights: string[];
  feature_importance: Array<{ feature: string; importance: number }>;
  best_setup: string | null;
  worst_session: string | null;
  evaluation: {
    accuracy: number | null;
    precision: number | null;
    recall: number | null;
    roc_auc: number | null;
    holdout_size: number;
    split_type: string;
    train_end_date: string | null;
    test_start_date: string | null;
  };
  sample_size: number;
}

export interface BacktestResult {
  strategyId: string | null;
  strategyVersion: string | null;
  strategyName: string | null;
  pair: string;
  setup: string;
  direction: string;
  timeframe: string | null;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  expectancyR: number;
  totalR: number;
  maxDrawdownR: number;
  equityCurve: Array<{ index: number; equity: number }>;
  sampleTrades: Array<{
    timestamp: string;
    entry: number;
    stopLoss: number;
    takeProfit: number;
    result: 'win' | 'loss';
    pnlR: number;
  }>;
  notes: string[];
}

export interface Strategy {
  id: string;
  name: string;
  version: string;
  pair: string;
  setup: 'breakout' | 'pullback' | 'reversal';
  direction: 'buy' | 'sell';
  timeframe: 'M5' | 'M15' | 'H1' | 'H4' | 'D1';
  riskReward: number;
  lookback: number;
  forwardBars: number;
  riskPercent: number;
  active: boolean;
  description: string | null;
  tags: string[] | null;
  createdAt: string;
}

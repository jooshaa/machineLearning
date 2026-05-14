import { Trade } from '../trades/trade.entity';

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

export function calculateAnalytics(trades: Trade[]): AnalyticsSnapshot {
  const sortedTrades = [...trades].sort(
    (a, b) => a.createdAt.getTime() - b.createdAt.getTime(),
  );

  const wins = sortedTrades.filter((trade) => trade.result === 'win');
  const losses = sortedTrades.filter((trade) => trade.result === 'loss');
  const totalProfit = sortedTrades.reduce((sum, trade) => sum + trade.profit, 0);
  const averageRiskReward =
    sortedTrades.length > 0
      ? sortedTrades.reduce((sum, trade) => sum + trade.riskReward, 0) /
        sortedTrades.length
      : 0;
  const grossProfit = wins.reduce((sum, trade) => sum + Math.max(trade.profit, 0), 0);
  const grossLoss = losses.reduce(
    (sum, trade) => sum + Math.abs(Math.min(trade.profit, 0)),
    0,
  );
  const equityCurve = buildEquityCurve(sortedTrades);
  const setupWinRates = getGroupedWinRates(sortedTrades, 'setup');
  const sessionWinRates = getGroupedWinRates(sortedTrades, 'session');
  const pairProfits = getGroupedAverage(sortedTrades, 'pair', 'profit');
  const averageConfidence =
    sortedTrades.length > 0
      ? sortedTrades.reduce((sum, trade) => sum + trade.confidence, 0) /
        sortedTrades.length
      : 0;

  return {
    totalTrades: sortedTrades.length,
    winRate: sortedTrades.length > 0 ? (wins.length / sortedTrades.length) * 100 : 0,
    averageRiskReward,
    profitFactor: grossLoss === 0 ? grossProfit : grossProfit / grossLoss,
    drawdown: calculateMaxDrawdown(equityCurve),
    totalProfit,
    equityCurve,
    bestSetup: getMaxKey(setupWinRates),
    weakestSession: getMinKey(sessionWinRates),
    bestPair: getMaxKey(pairProfits),
    averageConfidence,
    commonMistakes: getCommonMistakes(sortedTrades),
  };
}

function buildEquityCurve(trades: Trade[]) {
  let equity = 0;

  return trades.map((trade, index) => {
    equity += trade.profit;

    return {
      index: index + 1,
      equity,
    };
  });
}

function calculateMaxDrawdown(equityCurve: Array<{ index: number; equity: number }>) {
  let peak = 0;
  let maxDrawdown = 0;

  for (const point of equityCurve) {
    peak = Math.max(peak, point.equity);
    maxDrawdown = Math.max(maxDrawdown, peak - point.equity);
  }

  return maxDrawdown;
}

function getGroupedWinRates<T extends keyof Trade>(trades: Trade[], field: T) {
  const grouped = new Map<string, { wins: number; total: number }>();

  for (const trade of trades) {
    const key = String(trade[field] ?? 'Unknown');
    const current = grouped.get(key) ?? { wins: 0, total: 0 };
    current.total += 1;
    current.wins += trade.result === 'win' ? 1 : 0;
    grouped.set(key, current);
  }

  return new Map(
    [...grouped.entries()].map(([key, value]) => [key, value.wins / value.total]),
  );
}

function getGroupedAverage<T extends keyof Trade, N extends keyof Trade>(
  trades: Trade[],
  groupField: T,
  numericField: N,
) {
  const grouped = new Map<string, { total: number; count: number }>();

  for (const trade of trades) {
    const key = String(trade[groupField] ?? 'Unknown');
    const current = grouped.get(key) ?? { total: 0, count: 0 };
    current.total += Number(trade[numericField]);
    current.count += 1;
    grouped.set(key, current);
  }

  return new Map(
    [...grouped.entries()].map(([key, value]) => [key, value.total / value.count]),
  );
}

function getMaxKey(values: Map<string, number>) {
  if (values.size === 0) {
    return null;
  }

  return [...values.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

function getMinKey(values: Map<string, number>) {
  if (values.size === 0) {
    return null;
  }

  return [...values.entries()].sort((a, b) => a[1] - b[1])[0][0];
}

function getCommonMistakes(trades: Trade[]) {
  const counts = new Map<string, number>();

  for (const trade of trades) {
    if (!trade.mistake) {
      continue;
    }
    counts.set(trade.mistake, (counts.get(trade.mistake) ?? 0) + 1);
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([label, count]) => ({ label, count }));
}

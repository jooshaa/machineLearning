'use client';

import { useState } from 'react';
import { fetchCandles, runAdvancedBacktest } from '@/lib/api';
import { EquityCurve } from './equity-curve';

const SYMBOLS = [
  'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF',
  'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY', 'XAUUSD',
  'BTCUSD', 'ETHUSD', 'SPX500', 'NAS100', 'US30',
];

const TIMEFRAMES = [
  { value: 'M5', label: '5 Min' },
  { value: 'M15', label: '15 Min' },
  { value: 'H1', label: '1 Hour' },
  { value: 'H4', label: '4 Hour' },
  { value: 'D1', label: 'Daily' },
];

const PERIODS = [
  { value: '1mo', label: '1 Month' },
  { value: '3mo', label: '3 Months' },
  { value: '6mo', label: '6 Months' },
  { value: '1y', label: '1 Year' },
  { value: '2y', label: '2 Years' },
];

const INDICATORS = [
  'sma_10', 'sma_20', 'sma_50', 'sma_100', 'sma_200',
  'ema_10', 'ema_20', 'ema_50', 'ema_100', 'ema_200',
  'rsi_7', 'rsi_14', 'rsi_21',
  'macd', 'macd_signal', 'macd_hist',
  'bb_upper', 'bb_middle', 'bb_lower',
  'stoch_k', 'stoch_d', 'adx', 'atr_14',
];

const OPERATORS = [
  { value: 'above', label: 'Above' },
  { value: 'below', label: 'Below' },
  { value: 'crosses_above', label: 'Crosses above' },
  { value: 'crosses_below', label: 'Crosses below' },
];

interface Condition {
  indicator: string;
  operator: string;
  value: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type BacktestResultData = Record<string, any>;

export function AdvancedBacktest() {
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('H1');
  const [period, setPeriod] = useState('6mo');
  const [direction, setDirection] = useState<'buy' | 'sell'>('buy');
  const [slMult, setSlMult] = useState(1.5);
  const [tpMult, setTpMult] = useState(3.0);
  const [forwardBars, setForwardBars] = useState(20);

  const [entryConditions, setEntryConditions] = useState<Condition[]>([
    { indicator: 'rsi_14', operator: 'below', value: '30' },
  ]);

  const [candles, setCandles] = useState<Record<string, unknown>[]>([]);
  const [result, setResult] = useState<BacktestResultData | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'setup' | 'results'>('setup');

  const handleFetchCandles = async () => {
    setFetching(true);
    setError(null);
    try {
      const res = await fetchCandles({ symbol, interval: timeframe, period });
      setCandles(res.candles);
    } catch {
      setError('Failed to fetch candle data. Check symbol and try again.');
    } finally {
      setFetching(false);
    }
  };

  const addCondition = () => {
    setEntryConditions((prev) => [
      ...prev,
      { indicator: 'sma_50', operator: 'above', value: 'close' },
    ]);
  };

  const removeCondition = (idx: number) => {
    setEntryConditions((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateCondition = (idx: number, field: keyof Condition, val: string) => {
    setEntryConditions((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, [field]: val } : c)),
    );
  };

  const handleRunBacktest = async () => {
    if (candles.length < 50) {
      setError('Fetch at least 50 candles first.');
      return;
    }
    if (entryConditions.length === 0) {
      setError('Add at least one entry condition.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await runAdvancedBacktest({
        candles,
        direction,
        entry_conditions: entryConditions.map((c) => ({
          indicator: c.indicator,
          operator: c.operator,
          value: isNaN(Number(c.value)) ? c.value : Number(c.value),
        })),
        stop_loss_atr_mult: slMult,
        take_profit_atr_mult: tpMult,
        forward_bars: forwardBars,
        initial_balance: 10000,
      });
      setResult(res);
      setStep('results');
    } catch {
      setError('Backtest failed. Check conditions and try again.');
    } finally {
      setLoading(false);
    }
  };

  if (step === 'results' && result) {
    return (
      <ResultsDashboard
        result={result}
        symbol={symbol}
        timeframe={timeframe}
        onBack={() => setStep('setup')}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Data Source */}
      <div className="card p-5">
        <h3 className="mb-4 text-lg font-semibold">📡 Data source</h3>
        <div className="grid gap-4 md:grid-cols-4">
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Symbol</span>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded-xl border border-slate-300 px-4 py-2"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Timeframe</span>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="rounded-xl border border-slate-300 px-4 py-2"
            >
              {TIMEFRAMES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Period</span>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="rounded-xl border border-slate-300 px-4 py-2"
            >
              {PERIODS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleFetchCandles}
              disabled={fetching}
              className="rounded-full bg-sea px-5 py-2 text-sm font-medium text-white transition hover:opacity-90"
            >
              {fetching ? 'Fetching...' : 'Fetch data'}
            </button>
          </div>
        </div>
        {candles.length > 0 && (
          <p className="mt-3 text-sm text-sea font-medium">
            ✓ {candles.length} candles loaded
          </p>
        )}
      </div>

      {/* Strategy Rules */}
      <div className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">⚙️ Strategy rules</h3>
          <button
            type="button"
            onClick={addCondition}
            className="rounded-full border border-slate-300 px-4 py-1.5 text-sm text-slate-600 transition hover:border-sea hover:text-sea"
          >
            + Add condition
          </button>
        </div>

        <div className="mb-4 grid gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Direction</span>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as 'buy' | 'sell')}
              className="rounded-xl border border-slate-300 px-4 py-2"
            >
              <option value="buy">Buy (Long)</option>
              <option value="sell">Sell (Short)</option>
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">SL (ATR ×)</span>
            <input
              type="number"
              step="0.1"
              value={slMult}
              onChange={(e) => setSlMult(Number(e.target.value))}
              className="rounded-xl border border-slate-300 px-4 py-2"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">TP (ATR ×)</span>
            <input
              type="number"
              step="0.1"
              value={tpMult}
              onChange={(e) => setTpMult(Number(e.target.value))}
              className="rounded-xl border border-slate-300 px-4 py-2"
            />
          </label>
        </div>

        <div className="space-y-3">
          {entryConditions.map((cond, idx) => (
            <div key={idx} className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-400 uppercase">if</span>
              <select
                value={cond.indicator}
                onChange={(e) => updateCondition(idx, 'indicator', e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
              >
                {INDICATORS.map((ind) => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
              <select
                value={cond.operator}
                onChange={(e) => updateCondition(idx, 'operator', e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
              >
                {OPERATORS.map((op) => (
                  <option key={op.value} value={op.value}>{op.label}</option>
                ))}
              </select>
              <input
                value={cond.value}
                onChange={(e) => updateCondition(idx, 'value', e.target.value)}
                placeholder="30 or close"
                className="w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
              />
              <button
                type="button"
                onClick={() => removeCondition(idx)}
                className="text-sm text-coral hover:underline"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Run */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleRunBacktest}
          disabled={loading || candles.length < 50}
          className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Running backtest...' : '🚀 Run advanced backtest'}
        </button>
        {candles.length > 0 && candles.length < 50 && (
          <span className="text-sm text-coral">Need at least 50 candles</span>
        )}
      </div>

      {error && <div className="card p-5 text-sm text-coral">{error}</div>}
    </div>
  );
}

/* ---------- Results dashboard ---------- */

function ResultsDashboard({
  result,
  symbol,
  timeframe,
  onBack,
}: {
  result: BacktestResultData;
  symbol: string;
  timeframe: string;
  onBack: () => void;
}) {
  const equity: Array<{ index: number; equity: number }> = result.equity_curve ?? [];
  const monthly: Array<{
    month: string;
    trades: number;
    wins: number;
    win_rate: number;
    pnl_r: number;
  }> = result.monthly_breakdown ?? [];
  const trades: Array<Record<string, unknown>> = result.trades_list ?? [];
  const notes: string[] = result.notes ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            type="button"
            onClick={onBack}
            className="mb-2 text-sm text-sea hover:underline"
          >
            ← Back to setup
          </button>
          <h2 className="text-2xl font-semibold">
            Backtest results — {symbol} {timeframe}
          </h2>
        </div>
      </div>

      {/* Stat grid */}
      <div className="grid gap-4 md:grid-cols-4 lg:grid-cols-4">
        <StatCard label="Win Rate" value={`${result.win_rate ?? 0}%`} accent={result.win_rate >= 50} />
        <StatCard label="Profit Factor" value={String(result.profit_factor ?? 0)} accent={result.profit_factor > 1} />
        <StatCard label="Expectancy" value={`${result.expectancy_r ?? 0}R`} accent={result.expectancy_r > 0} />
        <StatCard label="Total Trades" value={String(result.total_trades ?? 0)} />
        <StatCard label="Wins / Losses" value={`${result.wins ?? 0} / ${result.losses ?? 0}`} />
        <StatCard label="Sharpe Ratio" value={String(result.sharpe_ratio ?? 0)} accent={result.sharpe_ratio > 1} />
        <StatCard label="Sortino Ratio" value={String(result.sortino_ratio ?? 0)} accent={result.sortino_ratio > 1} />
        <StatCard label="Max Drawdown" value={`${result.max_drawdown_r ?? 0}R`} negative />
        <StatCard label="Avg Win" value={`${result.avg_win_r ?? 0}R`} accent />
        <StatCard label="Avg Loss" value={`${result.avg_loss_r ?? 0}R`} negative />
        <StatCard label="Win Streak" value={String(result.max_win_streak ?? 0)} />
        <StatCard label="Loss Streak" value={String(result.max_loss_streak ?? 0)} negative />
        <StatCard label="Return %" value={`${result.return_pct ?? 0}%`} accent={result.return_pct > 0} />
        <StatCard label="Final Balance" value={`$${(result.final_balance ?? 0).toLocaleString()}`} />
        <StatCard label="Total R" value={`${result.total_r ?? 0}R`} accent={result.total_r > 0} />
        <StatCard label="Avg Holding" value={`${result.avg_holding_bars ?? 0} bars`} />
      </div>

      {/* Equity curve */}
      <EquityCurve points={equity} />

      {/* Notes */}
      {notes.length > 0 && (
        <div className="card p-5">
          <h3 className="mb-3 text-lg font-semibold">Strategy notes</h3>
          <div className="space-y-2">
            {notes.map((note, i) => (
              <div key={i} className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
                {note}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Monthly breakdown */}
      {monthly.length > 0 && (
        <div className="card overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <h3 className="text-lg font-semibold">Monthly breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-5 py-3">Month</th>
                  <th className="px-5 py-3">Trades</th>
                  <th className="px-5 py-3">Wins</th>
                  <th className="px-5 py-3">Win Rate</th>
                  <th className="px-5 py-3">PnL (R)</th>
                </tr>
              </thead>
              <tbody>
                {monthly.map((m) => (
                  <tr key={m.month} className="border-t border-slate-100">
                    <td className="px-5 py-3 font-medium">{m.month}</td>
                    <td className="px-5 py-3">{m.trades}</td>
                    <td className="px-5 py-3">{m.wins}</td>
                    <td className="px-5 py-3">{m.win_rate}%</td>
                    <td className={`px-5 py-3 font-medium ${m.pnl_r >= 0 ? 'text-sea' : 'text-coral'}`}>
                      {m.pnl_r > 0 ? '+' : ''}{m.pnl_r}R
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trade log */}
      {trades.length > 0 && (
        <div className="card overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <h3 className="text-lg font-semibold">Trade log (first {trades.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3">#</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Entry</th>
                  <th className="px-4 py-3">SL</th>
                  <th className="px-4 py-3">TP</th>
                  <th className="px-4 py-3">Exit</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">PnL (R)</th>
                  <th className="px-4 py-3">Bars</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-4 py-3 text-slate-400">{i + 1}</td>
                    <td className="px-4 py-3 text-xs">{String(t.timestamp).slice(0, 19)}</td>
                    <td className="px-4 py-3">{Number(t.entry).toFixed(4)}</td>
                    <td className="px-4 py-3">{Number(t.stop_loss).toFixed(4)}</td>
                    <td className="px-4 py-3">{Number(t.take_profit).toFixed(4)}</td>
                    <td className="px-4 py-3">{Number(t.exit_price).toFixed(4)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          t.result === 'win'
                            ? 'bg-teal-100 text-teal-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {String(t.result).toUpperCase()}
                      </span>
                    </td>
                    <td className={`px-4 py-3 font-medium ${Number(t.pnl_r) >= 0 ? 'text-sea' : 'text-coral'}`}>
                      {Number(t.pnl_r) > 0 ? '+' : ''}{Number(t.pnl_r).toFixed(2)}R
                    </td>
                    <td className="px-4 py-3">{String(t.holding_bars)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  negative,
}: {
  label: string;
  value: string;
  accent?: boolean;
  negative?: boolean;
}) {
  return (
    <div className="card p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold ${
          accent ? 'text-sea' : negative ? 'text-coral' : ''
        }`}
      >
        {value}
      </p>
    </div>
  );
}

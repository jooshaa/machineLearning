'use client';

import { useState } from 'react';
import { runBacktest } from '@/lib/api';
import { BacktestResult, Strategy } from '@/lib/types';
import { EquityCurve } from './equity-curve';

const sampleCandles = JSON.stringify(
  [
    { timestamp: '2026-04-01T09:00:00Z', open: 1.1, high: 1.102, low: 1.099, close: 1.101 },
    { timestamp: '2026-04-01T09:15:00Z', open: 1.101, high: 1.103, low: 1.1, close: 1.102 },
    { timestamp: '2026-04-01T09:30:00Z', open: 1.102, high: 1.104, low: 1.101, close: 1.103 },
    { timestamp: '2026-04-01T09:45:00Z', open: 1.103, high: 1.104, low: 1.1, close: 1.101 },
    { timestamp: '2026-04-01T10:00:00Z', open: 1.101, high: 1.105, low: 1.101, close: 1.104 },
    { timestamp: '2026-04-01T10:15:00Z', open: 1.104, high: 1.106, low: 1.103, close: 1.105 },
    { timestamp: '2026-04-01T10:30:00Z', open: 1.105, high: 1.107, low: 1.104, close: 1.106 },
    { timestamp: '2026-04-01T10:45:00Z', open: 1.106, high: 1.108, low: 1.105, close: 1.107 },
    { timestamp: '2026-04-01T11:00:00Z', open: 1.107, high: 1.109, low: 1.106, close: 1.108 },
    { timestamp: '2026-04-01T11:15:00Z', open: 1.108, high: 1.11, low: 1.107, close: 1.109 },
    { timestamp: '2026-04-01T11:30:00Z', open: 1.109, high: 1.111, low: 1.108, close: 1.11 },
    { timestamp: '2026-04-01T11:45:00Z', open: 1.11, high: 1.112, low: 1.109, close: 1.111 },
  ],
  null,
  2,
);

export function BacktestLab({ strategies }: { strategies: Strategy[] }) {
  const [payload, setPayload] = useState({
    strategyId: '',
    pair: 'EURUSD',
    setup: 'breakout',
    direction: 'buy',
    timeframe: 'M15',
    riskReward: 2,
    lookback: 4,
    candles: sampleCandles,
  });
  const [importMode, setImportMode] = useState<'json' | 'csv'>('json');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await runBacktest({
        strategyId: payload.strategyId || undefined,
        pair: payload.pair,
        setup: payload.setup,
        direction: payload.direction,
        timeframe: payload.timeframe,
        riskReward: Number(payload.riskReward),
        lookback: Number(payload.lookback),
        ...(importMode === 'json'
          ? { candles: JSON.parse(payload.candles) }
          : { csvContent: payload.candles }),
      });
      setResult(response);
    } catch {
      setError(
        importMode === 'json'
          ? 'Backtest failed. Check candle JSON formatting and backend availability.'
          : 'Backtest failed. Check candle CSV headers and backend availability.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="card grid gap-4 p-5 md:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Saved strategy</span>
          <select
            value={payload.strategyId}
            onChange={(event) =>
              setPayload((current) => ({ ...current, strategyId: event.target.value }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          >
            <option value="">Ad-hoc</option>
            {strategies.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name} ({strategy.version})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Pair</span>
          <input
            value={payload.pair}
            onChange={(event) => setPayload((current) => ({ ...current, pair: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Setup</span>
          <select
            value={payload.setup}
            onChange={(event) => setPayload((current) => ({ ...current, setup: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          >
            <option value="breakout">Breakout</option>
            <option value="pullback">Pullback</option>
            <option value="reversal">Reversal</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Direction</span>
          <select
            value={payload.direction}
            onChange={(event) => setPayload((current) => ({ ...current, direction: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Timeframe</span>
          <select
            value={payload.timeframe}
            onChange={(event) => setPayload((current) => ({ ...current, timeframe: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          >
            <option value="M5">M5</option>
            <option value="M15">M15</option>
            <option value="H1">H1</option>
            <option value="H4">H4</option>
            <option value="D1">D1</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Risk reward</span>
          <input
            type="number"
            step="0.1"
            value={payload.riskReward}
            onChange={(event) =>
              setPayload((current) => ({ ...current, riskReward: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Lookback candles</span>
          <input
            type="number"
            value={payload.lookback}
            onChange={(event) =>
              setPayload((current) => ({ ...current, lookback: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm md:col-span-2">
          <div className="flex items-center justify-between">
            <span className="text-slate-500">
              {importMode === 'json' ? 'Candles JSON' : 'Candle CSV'}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setImportMode('json')}
                className={`rounded-full px-3 py-1 text-xs ${
                  importMode === 'json' ? 'bg-ink text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                JSON
              </button>
              <button
                type="button"
                onClick={() => setImportMode('csv')}
                className={`rounded-full px-3 py-1 text-xs ${
                  importMode === 'csv' ? 'bg-ink text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                CSV
              </button>
            </div>
          </div>
          {importMode === 'csv' && (
            <label className="rounded-full border border-slate-300 px-4 py-2 text-center text-sm text-slate-700">
              Choose CSV
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) {
                    return;
                  }
                  void file.text().then((text) => {
                    setPayload((current) => ({ ...current, candles: text }));
                  });
                }}
              />
            </label>
          )}
          <textarea
            rows={16}
            value={payload.candles}
            onChange={(event) => setPayload((current) => ({ ...current, candles: event.target.value }))}
            className="rounded-2xl border border-slate-300 px-4 py-3 font-mono text-xs"
          />
        </label>
        <div className="md:col-span-2">
          <button
            type="button"
            onClick={handleRun}
            className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-white"
          >
            {loading ? 'Running backtest...' : 'Run backtest'}
          </button>
        </div>
      </div>

      {error && <div className="card p-5 text-sm text-coral">{error}</div>}

      {result && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <ResultCard label="Trades" value={String(result.trades)} />
            <ResultCard label="Win rate" value={`${result.winRate.toFixed(1)}%`} />
            <ResultCard label="Expectancy" value={`${result.expectancyR.toFixed(2)}R`} />
            <ResultCard label="Max DD" value={`${result.maxDrawdownR.toFixed(2)}R`} />
          </div>
          <div className="card p-5">
            <p className="text-sm text-slate-500">Strategy run</p>
            <p className="mt-2 text-lg font-semibold">
              {result.strategyName ?? 'Ad-hoc strategy'}
              {result.strategyVersion ? ` (${result.strategyVersion})` : ''}
            </p>
          </div>
          <EquityCurve points={result.equityCurve} />
          <div className="card p-5">
            <h2 className="text-lg font-semibold">Backtest notes</h2>
            <div className="mt-4 space-y-3">
              {result.notes.map((note) => (
                <div key={note} className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
                  {note}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ResultCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

'use client';

import React, { useState } from 'react';
import { runVolumeDeltaBacktest } from '@/lib/api';

export function VolumeDeltaBacktest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runVolumeDeltaBacktest();
      setResult(res);
    } catch (e: any) {
      setError(e.message || 'Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card-ink p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">🌊 Volume Delta Profile Strategy</h2>
        <button 
          onClick={handleRun} 
          disabled={loading} 
          className="btn-ink px-6 py-3"
        >
          {loading ? 'Running Backtest...' : '🚀 Run Backtest'}
        </button>
      </div>

      {error && <p className="text-coral text-center">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-slate-50 p-4 rounded-lg">
              <span className="text-slate-500 text-sm">Total Trades</span>
              <p className="text-2xl font-bold">{result.summary.total}</p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg">
              <span className="text-slate-500 text-sm">Win Rate</span>
              <p className="text-2xl font-bold">
                {result.summary.total > 0 ? ((result.summary.wins / result.summary.total) * 100).toFixed(1) : 0}%
              </p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg">
              <span className="text-slate-500 text-sm">Wins / Losses</span>
              <p className="text-2xl font-bold text-emerald-600">
                {result.summary.wins} <span className="text-slate-400">/</span> <span className="text-rose-600">{result.summary.losses}</span>
              </p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg">
              <span className="text-slate-500 text-sm">Avg R</span>
              <p className="text-2xl font-bold">{result.summary.avg_r.toFixed(2)}</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-left">Direction</th>
                  <th className="px-4 py-2 text-left">Entry</th>
                  <th className="px-4 py-2 text-left">TP</th>
                  <th className="px-4 py-2 text-left">SL</th>
                  <th className="px-4 py-2 text-left">Outcome</th>
                  <th className="px-4 py-2 text-left">R</th>
                </tr>
              </thead>
              <tbody>
                {result.signals.map((signal: any, index: number) => (
                  <tr key={index} className="border-t border-slate-100">
                    <td className="px-4 py-2">{signal.entry_time}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${signal.direction === 'buy' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                        {signal.direction.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2">{signal.entry_price.toFixed(2)}</td>
                    <td className="px-4 py-2">{signal.tp_price.toFixed(2)}</td>
                    <td className="px-4 py-2">{signal.sl_price.toFixed(2)}</td>
                    <td className="px-4 py-2">
                      <span className={`capitalize ${signal.outcome === 'win' ? 'text-emerald-600' : signal.outcome === 'loss' ? 'text-rose-600' : 'text-slate-500'}`}>
                        {signal.outcome}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono">{signal.r_multiple.toFixed(1)}R</td>
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

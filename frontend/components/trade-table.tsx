'use client';

import { useMemo, useState } from 'react';
import { analyzeTradeScreenshots, deleteTrade } from '@/lib/api';
import { Trade } from '@/lib/types';

export function TradeTable({ trades }: { trades: Trade[] }) {
  const [sessionFilter, setSessionFilter] = useState<string>('all');

  const filteredTrades = useMemo(() => {
    if (sessionFilter === 'all') {
      return trades;
    }

    return trades.filter((trade) => trade.session === sessionFilter);
  }, [sessionFilter, trades]);

  const handleDelete = async (id: string) => {
    await deleteTrade(id);
    window.location.reload();
  };

  const handleAnalyzeScreenshots = async (id: string) => {
    await analyzeTradeScreenshots(id);
    window.location.reload();
  };

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Trade journal</h2>
          <p className="text-sm text-slate-500">Filter and review execution context.</p>
        </div>
        <select
          value={sessionFilter}
          onChange={(event) => setSessionFilter(event.target.value)}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm"
        >
          <option value="all">All sessions</option>
          <option value="London">London</option>
          <option value="NY">NY</option>
          <option value="Asia">Asia</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-5 py-3">Pair</th>
              <th className="px-5 py-3">Ver</th>
              <th className="px-5 py-3">TF</th>
              <th className="px-5 py-3">Session</th>
              <th className="px-5 py-3">Setup</th>
              <th className="px-5 py-3">Direction</th>
              <th className="px-5 py-3">Conf</th>
              <th className="px-5 py-3">RR</th>
              <th className="px-5 py-3">Result</th>
              <th className="px-5 py-3">Profit</th>
              <th className="px-5 py-3">Emotion</th>
              <th className="px-5 py-3">Shots</th>
              <th className="px-5 py-3">Vision</th>
              <th className="px-5 py-3">Created</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {filteredTrades.map((trade) => (
              <tr key={trade.id} className="border-t border-slate-100">
                <td className="px-5 py-4 font-medium">{trade.pair}</td>
                <td className="px-5 py-4">{trade.strategyVersion}</td>
                <td className="px-5 py-4">{trade.timeframe ?? '-'}</td>
                <td className="px-5 py-4">{trade.session}</td>
                <td className="px-5 py-4 capitalize">{trade.setup}</td>
                <td className="px-5 py-4 uppercase">{trade.direction}</td>
                <td className="px-5 py-4">{trade.confidence}/5</td>
                <td className="px-5 py-4">{trade.riskReward.toFixed(2)}</td>
                <td className="px-5 py-4 capitalize">{trade.result}</td>
                <td
                  className={`px-5 py-4 font-medium ${
                    trade.profit >= 0 ? 'text-sea' : 'text-coral'
                  }`}
                >
                  {trade.profit.toFixed(2)}
                </td>
                <td className="px-5 py-4 capitalize">{trade.emotion ?? '-'}</td>
                <td className="px-5 py-4">
                  {trade.screenshotUrls?.length ? (
                    <a
                      href={`http://localhost:3001${trade.screenshotUrls[0]}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sea underline-offset-2 hover:underline"
                    >
                      {trade.screenshotUrls.length} file
                      {trade.screenshotUrls.length > 1 ? 's' : ''}
                    </a>
                  ) : (
                    '0'
                  )}
                </td>
                <td className="px-5 py-4">
                  <div className="flex max-w-xs flex-col gap-1">
                    <span className="text-xs capitalize text-slate-500">
                      {trade.screenshotAnalysisStatus}
                    </span>
                    {trade.screenshotSummary && (
                      <span className="truncate text-xs text-slate-700">
                        {trade.screenshotSummary}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-5 py-4">
                  {new Date(trade.createdAt).toLocaleDateString()}
                </td>
                <td className="px-5 py-4 text-right">
                  <div className="flex justify-end gap-2">
                    {trade.screenshotUrls?.length > 0 && (
                      <button
                        type="button"
                        onClick={() => handleAnalyzeScreenshots(trade.id)}
                        className="rounded-full border border-teal-300 px-3 py-1 text-xs text-teal-700"
                      >
                        Analyze
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(trade.id)}
                      className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filteredTrades.length === 0 && (
              <tr>
                <td colSpan={15} className="px-5 py-8 text-center text-slate-500">
                  No trades match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

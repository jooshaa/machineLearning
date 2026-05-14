'use client';

import { FormEvent, useState } from 'react';
import { createStrategy } from '@/lib/api';
import { Strategy } from '@/lib/types';

const initialState = {
  name: 'London breakout base',
  version: 'v1',
  pair: 'EURUSD',
  setup: 'breakout',
  direction: 'buy',
  timeframe: 'M15',
  riskReward: 2,
  lookback: 20,
  forwardBars: 7,
  riskPercent: 0.2,
  active: true,
  description: '',
  tags: '',
};

export function StrategyManager({ strategies }: { strategies: Strategy[] }) {
  const [formData, setFormData] = useState(initialState);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    await createStrategy({
      ...formData,
      tags: formData.tags
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      riskReward: Number(formData.riskReward),
      lookback: Number(formData.lookback),
      forwardBars: Number(formData.forwardBars),
      riskPercent: Number(formData.riskPercent),
    });
    window.location.reload();
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="card grid gap-4 p-5 md:grid-cols-3">
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Name</span>
          <input
            value={formData.name}
            onChange={(event) => setFormData((current) => ({ ...current, name: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Version</span>
          <input
            value={formData.version}
            onChange={(event) =>
              setFormData((current) => ({ ...current, version: event.target.value }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Pair</span>
          <input
            value={formData.pair}
            onChange={(event) => setFormData((current) => ({ ...current, pair: event.target.value }))}
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Setup</span>
          <select
            value={formData.setup}
            onChange={(event) => setFormData((current) => ({ ...current, setup: event.target.value }))}
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
            value={formData.direction}
            onChange={(event) =>
              setFormData((current) => ({ ...current, direction: event.target.value }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Timeframe</span>
          <select
            value={formData.timeframe}
            onChange={(event) =>
              setFormData((current) => ({ ...current, timeframe: event.target.value }))
            }
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
          <span className="text-slate-500">RR</span>
          <input
            type="number"
            step="0.1"
            value={formData.riskReward}
            onChange={(event) =>
              setFormData((current) => ({ ...current, riskReward: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Lookback</span>
          <input
            type="number"
            value={formData.lookback}
            onChange={(event) =>
              setFormData((current) => ({ ...current, lookback: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Forward bars</span>
          <input
            type="number"
            value={formData.forwardBars}
            onChange={(event) =>
              setFormData((current) => ({ ...current, forwardBars: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Risk percent</span>
          <input
            type="number"
            step="0.01"
            value={formData.riskPercent}
            onChange={(event) =>
              setFormData((current) => ({ ...current, riskPercent: Number(event.target.value) }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm md:col-span-2">
          <span className="text-slate-500">Description</span>
          <textarea
            rows={3}
            value={formData.description}
            onChange={(event) =>
              setFormData((current) => ({ ...current, description: event.target.value }))
            }
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-slate-500">Tags</span>
          <input
            value={formData.tags}
            onChange={(event) => setFormData((current) => ({ ...current, tags: event.target.value }))}
            placeholder="london, trend, momentum"
            className="rounded-xl border border-slate-300 px-4 py-2"
          />
        </label>
        <div className="md:col-span-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-white"
          >
            {saving ? 'Saving strategy...' : 'Save strategy'}
          </button>
        </div>
      </form>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold">Saved strategies</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Version</th>
                <th className="px-5 py-3">Pair</th>
                <th className="px-5 py-3">Setup</th>
                <th className="px-5 py-3">Dir</th>
                <th className="px-5 py-3">TF</th>
                <th className="px-5 py-3">RR</th>
                <th className="px-5 py-3">Lookback</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((strategy) => (
                <tr key={strategy.id} className="border-t border-slate-100">
                  <td className="px-5 py-4 font-medium">{strategy.name}</td>
                  <td className="px-5 py-4">{strategy.version}</td>
                  <td className="px-5 py-4">{strategy.pair}</td>
                  <td className="px-5 py-4 capitalize">{strategy.setup}</td>
                  <td className="px-5 py-4 uppercase">{strategy.direction}</td>
                  <td className="px-5 py-4">{strategy.timeframe}</td>
                  <td className="px-5 py-4">{Number(strategy.riskReward).toFixed(2)}</td>
                  <td className="px-5 py-4">{strategy.lookback}</td>
                </tr>
              ))}
              {strategies.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-slate-500">
                    No saved strategies yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


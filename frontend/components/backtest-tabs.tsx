'use client';

import { ReactNode, useState } from 'react';
import { FabioBacktest } from './fabio-backtest';
import { VolumeDeltaBacktest } from './volume-delta-backtest';

export function BacktestTabs({
  simpleContent,
  advancedContent,
}: {
  simpleContent: ReactNode;
  advancedContent: ReactNode;
}) {
  const [tab, setTab] = useState<'fabio' | 'advanced' | 'simple' | 'volume-delta'>('fabio');

  return (
    <div>
      <div className="mb-6 flex gap-2 overflow-x-auto pb-2">
        <button
          type="button"
          onClick={() => setTab('fabio')}
          className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition ${
            tab === 'fabio'
              ? 'bg-ink text-white shadow-md'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          💎 Fabio Core (Order Flow)
        </button>
        <button
          type="button"
          onClick={() => setTab('advanced')}
          className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition ${
            tab === 'advanced'
              ? 'bg-ink text-white shadow-md'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          ⚡ Advanced (Indicators)
        </button>
        <button
          type="button"
          onClick={() => setTab('simple')}
          className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition ${
            tab === 'simple'
              ? 'bg-ink text-white shadow-md'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          📊 Simple (Rule-based)
        </button>
        <button
          type="button"
          onClick={() => setTab('volume-delta')}
          className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition ${
            tab === 'volume-delta'
              ? 'bg-ink text-white shadow-md'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          🌊 Volume Delta
        </button>
      </div>
      {tab === 'fabio' && <FabioBacktest />}
      {tab === 'advanced' && advancedContent}
      {tab === 'simple' && simpleContent}
      {tab === 'volume-delta' && <VolumeDeltaBacktest />}
    </div>
  );
}

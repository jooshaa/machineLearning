'use client';

import { useState } from 'react';
import { importTradesCsv } from '@/lib/api';

export function TradeImportPanel() {
  const [csvContent, setCsvContent] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setCsvContent(await file.text());
  };

  const handleImport = async () => {
    setError(null);
    setStatus('Importing trades...');

    try {
      const response = await importTradesCsv(csvContent);
      setStatus(`Imported ${response.imported} trades.`);
      window.location.reload();
    } catch {
      setStatus(null);
      setError('Import failed. Check that your CSV includes pair/symbol and trade outcome fields.');
    }
  };

  return (
    <div className="card p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Import trade history</h2>
          <p className="text-sm text-slate-500">
            Upload CSV exports from TradingView, your broker, or a spreadsheet to train the model faster.
          </p>
        </div>
        <label className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-700">
          Choose CSV
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleFile(file);
              }
            }}
          />
        </label>
      </div>

      <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
        Supported headers include `pair` or `symbol`, `direction` or `side`, `entry_price`,
        `stop_loss`, `take_profit`, `risk_reward`, `profit` or `pnl`, `result`, `session`,
        `setup`, `strategy_version`, `timeframe`, `confidence`, `emotion`, `mistake`, `notes`,
        and `screenshot_urls`.
      </div>

      <textarea
        rows={10}
        value={csvContent}
        onChange={(event) => setCsvContent(event.target.value)}
        placeholder="Paste your trade CSV here if you don't want to upload a file."
        className="mt-4 w-full rounded-2xl border border-slate-300 px-4 py-3 font-mono text-xs"
      />

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleImport}
          disabled={!csvContent.trim()}
          className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          Import trades
        </button>
        {status && <span className="text-sm text-sea">{status}</span>}
        {error && <span className="text-sm text-coral">{error}</span>}
      </div>
    </div>
  );
}

'use client';

import React, { useState, useEffect, useRef } from 'react';
import { runVolumeDeltaBacktest, fetchLocalCandles } from '@/lib/api';
import { createChart, CandlestickSeries, createSeriesMarkers, Time, SeriesMarker, ColorType } from 'lightweight-charts';

const TIMEFRAMES = ['1m', '5m', '15m', '1H'] as const;
type Timeframe = typeof TIMEFRAMES[number];

export function VolumeDeltaBacktest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<any>(null);
  const [candles, setCandles] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [timeframe, setTimeframe] = useState<Timeframe>('5m');

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runVolumeDeltaBacktest();
      setResult(res);
      setSelectedSignal(null);
      setCandles([]);
    } catch (e: any) {
      setError(e.message || 'Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  // Fetch full-day candles whenever signal or timeframe changes
  useEffect(() => {
    async function loadCandles() {
      if (!selectedSignal) return;

      setChartLoading(true);
      try {
        const date = selectedSignal.entry_time.substring(0, 10);
        const res = await fetchLocalCandles(date, timeframe);
        setCandles(res.candles);
      } catch (e) {
        console.error('Failed to fetch candles', e);
      } finally {
        setChartLoading(false);
      }
    }
    loadCandles();
  }, [selectedSignal, timeframe]);

  // Build chart when candles or signal change
  useEffect(() => {
    if (!chartContainerRef.current || candles.length === 0 || !selectedSignal) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // Show full trading day — no time window filter
    const chartData = candles
      .filter(c => c.open && c.high && c.low && c.close)
      .map(c => ({
        time: (new Date(c.timestamp as string).getTime() / 1000) as Time,
        open: c.open as number,
        high: c.high as number,
        low: c.low as number,
        close: c.close as number,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));

    candlestickSeries.setData(chartData);

    // Find the candle closest to entry time for marker placement
    const tradeTime = new Date(selectedSignal.entry_time).getTime() / 1000;
    let closestCandleTime = chartData[0]?.time as number;
    for (let i = chartData.length - 1; i >= 0; i--) {
      if ((chartData[i].time as number) <= tradeTime) {
        closestCandleTime = chartData[i].time as number;
        break;
      }
    }

    // Outcome colour: green = win, red = loss, yellow = timeout
    let markerColor = '#eab308';
    if (selectedSignal.outcome === 'win') markerColor = '#10b981';
    if (selectedSignal.outcome === 'loss') markerColor = '#ef4444';

    createSeriesMarkers(candlestickSeries, [
      {
        time: closestCandleTime as Time,
        position: selectedSignal.direction === 'buy' ? 'belowBar' : 'aboveBar',
        color: markerColor,
        shape: selectedSignal.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${selectedSignal.direction.toUpperCase()} — ${selectedSignal.outcome.toUpperCase()}`,
      } as SeriesMarker<Time>,
    ]);

    // Fix 1: Use sl_price and tp_price directly from signal — they are already correct
    // TP — green dashed line
    candlestickSeries.createPriceLine({
      price: selectedSignal.tp_price,
      color: '#10b981',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: 'TP',
    });

    // SL — red dashed line (sl_price is already below entry for BUY, above for SELL)
    candlestickSeries.createPriceLine({
      price: selectedSignal.sl_price,
      color: '#ef4444',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: 'SL',
    });

    // Entry — blue solid line
    candlestickSeries.createPriceLine({
      price: selectedSignal.entry_price,
      color: '#6366f1',
      lineWidth: 1,
      lineStyle: 0, // Solid
      axisLabelVisible: true,
      title: 'Entry',
    });

    // Auto-scroll to the entry region (±4h) instead of fitting the whole day
    const viewFrom = (tradeTime - 4 * 3600) as Time;
    const viewTo = (tradeTime + 4 * 3600) as Time;
    chart.timeScale().setVisibleRange({ from: viewFrom, to: viewTo });

    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, selectedSignal]);

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
                  <tr
                    key={index}
                    className={`border-t border-slate-100 cursor-pointer hover:bg-slate-50 ${selectedSignal === signal ? 'bg-indigo-50 border-l-2 border-l-indigo-400' : ''}`}
                    onClick={() => setSelectedSignal(signal)}
                  >
                    <td className="px-4 py-2 font-mono text-xs">{signal.entry_time}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${signal.direction === 'buy' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                        {signal.direction.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono">{signal.entry_price.toFixed(2)}</td>
                    <td className="px-4 py-2 font-mono text-emerald-600">{signal.tp_price.toFixed(2)}</td>
                    <td className="px-4 py-2 font-mono text-rose-600">{signal.sl_price.toFixed(2)}</td>
                    <td className="px-4 py-2">
                      <span className={`capitalize font-medium ${signal.outcome === 'win' ? 'text-emerald-600' : signal.outcome === 'loss' ? 'text-rose-600' : 'text-slate-400'}`}>
                        {signal.outcome}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono">{signal.r_multiple.toFixed(1)}R</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedSignal && (
            <div className="mt-6 border-t border-slate-100 pt-6">
              <div className="flex justify-between items-start mb-4 flex-wrap gap-3">
                <div>
                  <h3 className="text-lg font-bold">
                    {selectedSignal.direction === 'buy' ? '🟢' : '🔴'} {selectedSignal.direction.toUpperCase()} @ {selectedSignal.entry_price.toFixed(2)}
                  </h3>
                  <p className="text-sm text-slate-500">
                    {selectedSignal.entry_time} &nbsp;·&nbsp;
                    <span className="text-emerald-600">TP {selectedSignal.tp_price.toFixed(2)}</span>
                    &nbsp;·&nbsp;
                    <span className="text-rose-600">SL {selectedSignal.sl_price.toFixed(2)}</span>
                    &nbsp;·&nbsp;
                    <span className={selectedSignal.outcome === 'win' ? 'text-emerald-600 font-semibold' : selectedSignal.outcome === 'loss' ? 'text-rose-600 font-semibold' : 'text-slate-400'}>
                      {selectedSignal.outcome.toUpperCase()} {selectedSignal.r_multiple.toFixed(1)}R
                    </span>
                  </p>
                </div>

                {/* Fix 3 — Timeframe switcher */}
                <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                  {TIMEFRAMES.map(tf => (
                    <button
                      key={tf}
                      onClick={() => setTimeframe(tf)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                        timeframe === tf
                          ? 'bg-white text-indigo-600 shadow-sm'
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                  {chartLoading && <span className="text-xs text-slate-400 ml-2">Loading...</span>}
                </div>
              </div>

              <div
                ref={chartContainerRef}
                className="w-full bg-white rounded-lg border border-slate-100"
                style={{ minHeight: '420px' }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

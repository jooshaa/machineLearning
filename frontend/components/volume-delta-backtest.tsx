'use client';

import React, { useState, useEffect, useRef } from 'react';
import { runVolumeDeltaBacktest, fetchLocalCandles } from '@/lib/api';
import { createChart, CandlestickSeries, createSeriesMarkers, Time, SeriesMarker, ColorType } from 'lightweight-charts';


export function VolumeDeltaBacktest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<any>(null);
  const [candles, setCandles] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  
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

  useEffect(() => {
    async function loadCandles() {
      if (!selectedSignal) return;
      
      setChartLoading(true);
      try {
        const date = selectedSignal.entry_time.substring(0, 10);
        const res = await fetchLocalCandles(date);
        setCandles(res.candles);
      } catch (e) {
        console.error('Failed to fetch candles', e);
      } finally {
        setChartLoading(false);
      }
    }
    loadCandles();
  }, [selectedSignal]);

  useEffect(() => {
    if (!chartContainerRef.current || candles.length === 0 || !selectedSignal) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
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

    const chartData = candles
      .filter(c => c.open && c.high && c.low && c.close)
      .map(c => ({
        time: (new Date(c.timestamp as string).getTime() / 1000) as Time,
        open: c.open as number,
        high: c.high as number,
        low: c.low as number,
        close: c.close as number,
      })).sort((a, b) => (a.time as number) - (b.time as number));

    candlestickSeries.setData(chartData);

    // Add Marker
    const tradeTime = (new Date(selectedSignal.entry_time).getTime() / 1000) as Time;
    
    // Find closest candle time to avoid offset issues
    let closestCandleTime = chartData[0]?.time as number;
    for (let i = chartData.length - 1; i >= 0; i--) {
      if ((chartData[i].time as number) <= (tradeTime as number)) {
        closestCandleTime = chartData[i].time as number;
        break;
      }
    }

    let color = '#eab308'; // Default timeout yellow
    if (selectedSignal.outcome === 'win') color = '#10b981';
    if (selectedSignal.outcome === 'loss') color = '#ef4444';

    createSeriesMarkers(candlestickSeries, [
      {
        time: closestCandleTime as Time,
        position: selectedSignal.direction === 'buy' ? 'belowBar' : 'aboveBar',
        color: color,
        shape: selectedSignal.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        text: selectedSignal.outcome.toUpperCase(),
      } as SeriesMarker<Time>
    ]);

    // Add Price Lines
    candlestickSeries.createPriceLine({
      price: selectedSignal.tp_price,
      color: '#10b981',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: 'TP',
    });

    candlestickSeries.createPriceLine({
      price: selectedSignal.sl_price,
      color: '#ef4444',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: 'SL',
    });

    chart.timeScale().fitContent();
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
                    className={`border-t border-slate-100 cursor-pointer hover:bg-slate-50 ${selectedSignal === signal ? 'bg-slate-100' : ''}`}
                    onClick={() => setSelectedSignal(signal)}
                  >
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

          {selectedSignal && (
            <div className="mt-6 border-t border-slate-100 pt-6">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="text-lg font-bold">Chart for {selectedSignal.entry_time}</h3>
                  <p className="text-sm text-slate-500">
                    {selectedSignal.direction.toUpperCase()} @ {selectedSignal.entry_price.toFixed(2)} | 
                    TP: {selectedSignal.tp_price.toFixed(2)} | 
                    SL: {selectedSignal.sl_price.toFixed(2)}
                  </p>
                </div>
                {chartLoading && <span className="text-sm text-slate-400">Loading candles...</span>}
              </div>
              <div ref={chartContainerRef} className="w-full bg-white rounded-lg border border-slate-100" style={{ minHeight: '400px' }} />
            </div>
          )}
        </div>
      )}

    </div>
  );
}

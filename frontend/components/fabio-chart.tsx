'use client';
import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, SeriesMarker, Time, CandlestickSeries, createSeriesMarkers } from 'lightweight-charts';

interface Trade {
  time: string;
  dir: 'Long' | 'Short';
  entry: number;
  result: 'win' | 'loss' | 'breakeven';
  pnl?: number;
  isStrategy?: boolean;
}

interface ChartProps {
  candles: any[];
  trades?: Trade[];
}

export const FabioChart: React.FC<ChartProps> = ({ candles, trades = [] }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [strategyTrades, setStrategyTrades] = useState<any[]>([]);
  const [showStrategySignals, setShowStrategySignals] = useState(false);

  useEffect(() => {
    if (showStrategySignals && strategyTrades.length === 0) {
      fetch('/volume_delta_trades.json')
        .then(res => res.json())
        .then(data => setStrategyTrades(data))
        .catch(err => console.error("Failed to load strategy signals", err));
    }
  }, [showStrategySignals, strategyTrades]);

  useEffect(() => {
    console.log("FabioChart useEffect triggered, candles:", candles?.length);

    if (!chartContainerRef.current || candles.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: Time) => {
          const d = new Date((time as number) * 1000);
          return d.toLocaleDateString() + ' ' + d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
        },
      },
      localization: {
        timeFormatter: (time: Time) => {
          const d = new Date((time as number) * 1000);
          return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        }
      }
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // Format candles for lightweight-charts
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

    // Add Trade Markers
    const allTrades = [...trades];
    if (showStrategySignals) {
      strategyTrades.forEach(st => {
        allTrades.push({
          time: st.time,
          dir: st.dir,
          entry: st.entry,
          result: st.result,
          pnl: st.r,
          isStrategy: true
        });
      });
    }

    if (allTrades.length > 0 && chartData.length > 0) {
      // Calculate a time shift if trades are from a different year (e.g. MBO from 2023 vs YF 2026)
      const lastTradeTime = new Date(allTrades[allTrades.length - 1].time).getTime() / 1000;
      const lastCandleTime = chartData[chartData.length - 1].time as number;
      const firstCandleTime = chartData[0].time as number;
      
      let timeShift = 0;

      // Group trades by their snapped candle time to prevent massive vertical stacking
      const groupedMarkers = new Map<number, { pnl: number, count: number, dir: string, result: string }>();
      
      allTrades.forEach(t => {
        const tradeTime = (new Date(t.time).getTime() / 1000) + timeShift;
        let closestCandleTime = chartData[0].time as number;
        for (let i = chartData.length - 1; i >= 0; i--) {
          if ((chartData[i].time as number) <= tradeTime) {
            closestCandleTime = chartData[i].time as number;
            break;
          }
        }
        
        const pnl = t.pnl || (t.result === 'win' ? 1 : -1);
        if (groupedMarkers.has(closestCandleTime)) {
            const existing = groupedMarkers.get(closestCandleTime)!;
            existing.pnl += pnl;
            existing.count += 1;
            existing.dir = t.dir;
            existing.result = t.result;
        } else {
            groupedMarkers.set(closestCandleTime, { pnl, count: 1, dir: t.dir, result: t.result });
        }
      });

      const markers: SeriesMarker<Time>[] = Array.from(groupedMarkers.entries()).map(([time, data]) => {
          const isWin = data.pnl > 0;
          const isLong = data.dir === 'Long';
          
          return {
              time: time as Time,
              position: isLong ? 'belowBar' : 'aboveBar',
              color: isLong ? (isWin ? '#10b981' : '#a7f3d0') : (isWin ? '#ef4444' : '#fecaca'),
              shape: isLong ? 'arrowUp' : 'arrowDown',
              text: data.count > 1 ? `${data.pnl > 0 ? '+' : ''}${data.pnl.toFixed(1)}R (${data.count}t)` : `${data.pnl > 0 ? '+' : ''}${data.pnl.toFixed(1)}R`,
          } as SeriesMarker<Time>;
      }).sort((a, b) => (a.time as number) - (b.time as number));

      createSeriesMarkers(candlestickSeries, markers);
    }

    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles, trades]);

  return (
    <div className="w-full bg-slate-900/40 rounded-xl border border-slate-800 p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-white">Chart</h3>
        <button
          onClick={() => setShowStrategySignals(!showStrategySignals)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            showStrategySignals 
              ? 'bg-emerald-500 text-white' 
              : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
          }`}
        >
          {showStrategySignals ? 'Hide Strategy Signals' : 'Strategy Signals'}
        </button>
      </div>
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};

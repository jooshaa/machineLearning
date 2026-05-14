'use client';
import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, SeriesMarker, Time, CandlestickSeries, createSeriesMarkers } from 'lightweight-charts';

interface Trade {
  time: string;
  dir: 'Long' | 'Short';
  entry: number;
  result: 'win' | 'loss' | 'breakeven';
}

interface ChartProps {
  candles: any[];
  trades?: Trade[];
}

export const FabioChart: React.FC<ChartProps> = ({ candles, trades = [] }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

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
    if (trades.length > 0 && chartData.length > 0) {
      // Calculate a time shift if trades are from a different year (e.g. MBO from 2023 vs YF 2026)
      const lastTradeTime = new Date(trades[trades.length - 1].time).getTime() / 1000;
      const lastCandleTime = chartData[chartData.length - 1].time as number;
      const firstCandleTime = chartData[0].time as number;
      
      let timeShift = 0;

      // Group trades by their snapped candle time to prevent massive vertical stacking
      const groupedMarkers = new Map<number, { pnl: number, count: number }>();
      
      trades.forEach(t => {
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
        } else {
            groupedMarkers.set(closestCandleTime, { pnl, count: 1 });
        }
      });

      const markers: SeriesMarker<Time>[] = Array.from(groupedMarkers.entries()).map(([time, data]) => ({
          time: time as Time,
          position: data.pnl > 0 ? 'belowBar' : 'aboveBar',
          color: data.pnl > 0 ? '#10b981' : '#ef4444',
          shape: data.pnl > 0 ? 'arrowUp' : 'arrowDown',
          text: data.count > 1 ? `${data.pnl > 0 ? '+' : ''}${data.pnl.toFixed(1)}R (${data.count}t)` : `${data.pnl > 0 ? '+' : ''}${data.pnl.toFixed(1)}R`,
      })).sort((a, b) => (a.time as number) - (b.time as number));

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
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};

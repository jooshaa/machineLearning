'use client';

import { useState, useEffect } from 'react';
import { FabioChart } from './fabio-chart';
import { fetchCandles, getFabioHistory, getFabioMemory, runFabioBacktest, saveFabioResult, trainFabioAi, startFabioL3, getFabioL3Status, getFabioL3Result, cancelFabioL3, getFabioL3Analysis, fetchLocalCandles } from '@/lib/api';
import { EquityCurve } from './equity-curve';

const SYMBOLS = ['NQ', 'ES', 'EURUSD', 'GBPUSD', 'XAUUSD', 'BTCUSD', 'ETHUSD'];

function getPrevTradingDays(dateStr: string, n: number): string[] {
    const days = [];
    let d = new Date(dateStr);
    while (days.length < n) {
        if (d.getDay() !== 0 && d.getDay() !== 6) days.unshift(d.toISOString().split('T')[0]);
        d.setDate(d.getDate() - 1);
    }
    return days;
}

export function FabioBacktest() {
  const [symbol, setSymbol] = useState('NQ');
  const [timeframe, setTimeframe] = useState('H1');
  const [period, setPeriod] = useState('3mo');
  const [session, setSession] = useState<'all' | 'london' | 'newyork'>('all');
  const [startDate, setStartDate] = useState('2023-01-05');
  const [startTime, setStartTime] = useState('14:30');
  const [endDate, setEndDate] = useState('');
  
  // Fabio Params
  const [vpPeriod, setVpPeriod] = useState(50);
  const [vaPct, setVaPct] = useState(0.70);
  const [followBars, setFollowBars] = useState(5);
  const [slMult, setSlMult] = useState(1.5);
  const [tpMult, setTpMult] = useState(3.0);
  const [enableTrap, setEnableTrap] = useState(true);
  const [enableAbsorption, setEnableAbsorption] = useState(true);
  const [enableSqueeze, setEnableSqueeze] = useState(true);
  const [useMBO, setUseMBO] = useState(false);
  const [discoveryMode, setDiscoveryMode] = useState(false);
  const [useValidation, setUseValidation] = useState(true); // New: strict validation toggle

  // Auto-correct period for low timeframes (Yahoo Finance limits)
  useEffect(() => {
    if (['M5', 'M15', 'M30'].includes(timeframe)) {
      if (['3mo', '6mo', '1y'].includes(period)) {
        setPeriod('1mo');
      }
    }
  }, [timeframe, period]);

  const [candles, setCandles] = useState<Record<string, unknown>[]>([]);
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'setup' | 'results' | 'history' | 'ai_memory'>('setup');

  // Async MBO States
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStage, setJobStage] = useState<string>('');
  const [progress, setProgress] = useState(0);

  // Polling Effect
  useEffect(() => {
    let interval: any;
    if (jobId && loading) {
      interval = setInterval(async () => {
        try {
          const status = await getFabioL3Status(jobId);
          setJobStage(status.stage);
          setProgress(status.progress);

          if (status.status === 'done') {
            const final = await getFabioL3Result(jobId);
            setResult(transformMBOResult(final));
            
            // Загружаем свечи за неделю (5 торговых дней)
            try {
              const dates = getPrevTradingDays(startDate, 5);
              const allCandles = [];
              for (const d of dates) {
                try {
                  const res = await fetchLocalCandles(d);
                  allCandles.push(...(res.candles || []));
                } catch {}
              }
              allCandles.sort((a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
              setCandles(allCandles);
              console.log("Multi-day candles loaded:", allCandles.length);
            } catch (e) {
              console.error("Failed to fetch local candles", e);
            }

            setStep('results');
            setLoading(false);
            setJobId(null);
            clearInterval(interval);
          } else if (status.status === 'error') {
            setError(status.error || 'Job failed');
            setLoading(false);
            setJobId(null);
            clearInterval(interval);
          } else if (status.status === 'cancelled') {
            setLoading(false);
            setJobId(null);
            clearInterval(interval);
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [jobId, loading]);
  const transformMBOResult = (res: any) => {
    if (!res) return null;
    const trades = res.trades || [];
    const rawStats = res.stats || {};
    
    const trades_list = trades.map((t: any) => ({
      time: t.timestamp || t.ts,
      setup: t.setup || t.event_type || 'Unknown',
      dir: t.direction === 'buy' ? 'Long' : 'Short',
      entry: t.entry_price || t.entry,
      sl: t.stop_loss || t.stop,
      tp: t.take_profit || t.target,
      exit: t.exit_price || t.exit,
      why: t.exit_reason || t.exit_type || '',
      result: t.result,
      pnl: t.pnl_r || t.outcome_R || 0,
      bars: t.holding_bars || 0,
      conf: t.confluence || Math.round((t.score || 0) * 5),
      tier: t.risk_tier || (t.size_mult > 1.5 ? 'High' : 'Standard'),
      ai: t.ai_score || 0,
      note: t.note || t.regime || ''
    }));

    // Calculate missing dashboard stats if not provided (especially for L3 results)
    const finished = trades_list.filter((t: any) => t.result === 'win' || t.result === 'loss');
    const wins = finished.filter((t: any) => t.result === 'win');
    const losses = finished.filter((t: any) => t.result === 'loss');
    
    const win_rate = finished.length > 0 ? (wins.length / finished.length) * 100 : 0;
    const total_r = finished.reduce((sum: number, t: any) => sum + t.pnl, 0);
    const gross_profit = wins.reduce((sum: number, t: any) => sum + t.pnl, 0);
    const gross_loss = Math.abs(losses.reduce((sum: number, t: any) => sum + t.pnl, 0));
    const profit_factor = gross_loss === 0 ? (gross_profit > 0 ? 99 : 0) : (gross_profit / gross_loss);
    const expectancy_r = finished.length > 0 ? total_r / finished.length : 0;
    
    let current_eq = 0;
    let peak_eq = 0;
    let max_drawdown_r = 0;
    const equity_curve = finished.map((t: any, i: number) => {
        current_eq += t.pnl;
        if (current_eq > peak_eq) peak_eq = current_eq;
        const dd = peak_eq - current_eq;
        if (dd > max_drawdown_r) max_drawdown_r = dd;
        return { index: i + 1, equity: current_eq };
    });

    const stats = {
      ...rawStats,
      total_trades: rawStats.total_trades || finished.length,
      win_rate: Number((rawStats.win_rate || win_rate).toFixed(1)),
      total_r: Number((rawStats.total_r ?? rawStats.total_R ?? total_r).toFixed(2)),
      profit_factor: Number((rawStats.profit_factor || profit_factor).toFixed(2)),
      expectancy_r: Number((rawStats.expectancy_r || expectancy_r).toFixed(2)),
      max_drawdown_r: Number((rawStats.max_drawdown_r || max_drawdown_r).toFixed(2)),
      equity_curve: rawStats.equity_curve || equity_curve,
      return_pct: Number((rawStats.return_pct || (total_r * 0.25)).toFixed(2)),
      avg_holding_bars: rawStats.avg_holding_bars || 0,
      sharpe_ratio: rawStats.sharpe_ratio || 0,
      sortino_ratio: rawStats.sortino_ratio || 0
    };

    return {
      ...stats,
      trades_list
    };
  };

  const handleCancel = async () => {
    if (jobId) {
      await cancelFabioL3(jobId);
      setLoading(false);
      setJobId(null);
      setError("Analysis cancelled by user.");
    }
  };

  const handleFetch = async () => {
    setFetching(true);
    try {
      let finalPeriod = period;
      // Yahoo Finance sometimes rejects 1mo for NQ=F 5m/15m data, fallback to 20d
      if (['M1', 'M5', 'M15', 'M30'].includes(timeframe)) {
          if (period === '1mo' || period === '3mo' || period === '6mo') {
              finalPeriod = timeframe === 'M1' ? '5d' : '20d';
          }
      }
      const res = await fetchCandles({ symbol, interval: timeframe, period: finalPeriod });
      setCandles(res.candles);
    } catch (err: any) {
      const msg = err.message || 'Failed to fetch data';
      if (msg.includes('No data found') || msg.includes('404')) {
        setError(`No candle data for ${symbol} on ${timeframe}. Yahoo Finance doesn't support all timeframes for futures. Try H1 (1 hour).`);
      } else {
        setError(msg);
      }
    } finally {
      setFetching(false);
    }
  };

  const handleRun = async () => {
    if (!useMBO && candles.length < 80) return setError('Need 80+ candles for candle-based backtest');
    setLoading(true);
    setError(null);
    try {
      if (useMBO) {
        const startISO = `${startDate}T${startTime}:00`;
        const [h, m] = startTime.split(':').map(Number);
        const endH = (h + 2).toString().padStart(2, '0');
        const endISO = `${startDate}T${endH}:${m.toString().padStart(2, '0')}:00`;

        const res = await startFabioL3({
          symbol: symbol + ".FUT",
          start: startISO,
          end: endISO,
          discovery_mode: discoveryMode,
          use_validated_edge: useValidation
        });
        setJobId(res.job_id);
        setJobStage('starting');
        setProgress(0);
        return; 
      } else {
        const res = await runFabioBacktest({
          candles,
          vp_period: vpPeriod,
          value_area_pct: vaPct,
          follow_bars: followBars,
          sl_atr_mult: slMult,
          tp_atr_mult: tpMult,
          enable_trap: enableTrap,
          enable_absorption: enableAbsorption,
          enable_squeeze: enableSqueeze,
          enable_cvd_divergence: true,
          session_filter: session,
          model_type: 'both',
          initial_balance: 10000,
          trap_confirm_bars: 3,
          absorption_repeat: 2,
          squeeze_retest_bars: 8,
        });
        setResult(res);
      }
      setStep('results');
    } catch (err: any) {
      setError(err.message || 'Backtest failed');
      setLoading(false);
    } finally {
      if (!useMBO) setLoading(false);
    }
  };

  if (step === 'results' && result) {
    return (
      <FabioResults 
        result={result} 
        symbol={symbol}
        timeframe={timeframe}
        period={period}
        session={session}
        candles={candles}
        params={{
          vpPeriod, vaPct, followBars, slMult, tpMult, 
          enableTrap, enableAbsorption, enableSqueeze
        }}
        onBack={() => setStep('setup')} 
      />
    );
  }

  if (step === 'history') {
    return <FabioHistory onBack={() => setStep('setup')} onSelect={(r: any) => {
      setResult(r.full_result);
      setStep('results');
    }} />;
  }

  if (step === 'ai_memory') {
    return <FabioAiMemory onBack={() => setStep('setup')} />;
  }

  if (step === ('analysis' as any)) {
    return <FabioEdgeAnalysis onBack={() => setStep('setup')} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center flex-wrap gap-3">
        <h2 className="text-xl font-bold">Fabio Valentino Strategy</h2>
        <div className="flex gap-4">
          <button onClick={() => setStep('ai_memory')} className="text-sm font-medium text-violet-600 hover:text-violet-800">
            🧠 View AI Memory
          </button>
          <button onClick={() => setStep('history')} className="text-sm font-medium text-slate-500 hover:text-ink">
            📜 History
          </button>
          <button onClick={() => setStep('analysis' as any)} className="text-sm font-medium text-indigo-600 hover:text-ink">
            🛡️ Stability Dashboard
          </button>
        </div>
      </div>
      <div className="card p-5">
        <h3 className="mb-4 text-lg font-semibold">📍 Market Context</h3>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Symbol</span>
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="input-select">
              {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Timeframe (Chart)</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="input-select">
              <option value="M1">M1 (1 min)</option>
              <option value="M5">M5 (5 min)</option>
              <option value="M15">M15 (15 min)</option>
              <option value="M30">M30 (30 min)</option>
              <option value="H1">H1 (1 hour)</option>
              <option value="H4">H4 (4 hours)</option>
              <option value="D1">D1 (Daily)</option>
              <option value="W1">W1 (Weekly)</option>
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Data Period</span>
            <select value={period} onChange={(e) => setPeriod(e.target.value)} className="input-select">
              <option value="1mo">1 Month</option>
              <option value="3mo" disabled={['M5', 'M15', 'M30'].includes(timeframe)}>3 Months (H1+ only)</option>
              <option value="6mo" disabled={['M5', 'M15', 'M30'].includes(timeframe)}>6 Months (H1+ only)</option>
              <option value="1y" disabled={['M5', 'M15', 'M30'].includes(timeframe)}>1 Year (H1+ only)</option>
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-slate-500">Session Filter</span>
            <select value={session} onChange={(e) => setSession(e.target.value as any)} className="input-select">
              <option value="all">Full Day (24h)</option>
              <option value="london">London (08:00 - 17:00 UTC)</option>
              <option value="newyork">New York (13:00 - 22:00 UTC)</option>
            </select>
          </label>
          <div className="flex flex-col gap-2 text-sm justify-end">
            <span className="text-[10px] text-slate-400 bg-slate-50 rounded px-2 py-1 text-center">
              {timeframe} × {period} 
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-4">
          <button onClick={handleFetch} disabled={fetching} className="btn-primary px-8">
            {fetching ? '...' : 'Fetch Candles'}
          </button>
          {candles.length > 0 && <span className="text-sea text-sm font-medium">✓ {candles.length} bars loaded</span>}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-4 text-lg font-semibold">⚙️ Volume Profile & Follow-through</h3>
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-sm">VP Lookback Bars</span>
              <input type="number" value={vpPeriod} onChange={e => setVpPeriod(+e.target.value)} className="w-20 text-right font-medium" />
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Value Area %</span>
              <input type="number" step="0.05" value={vaPct} onChange={e => setVaPct(+e.target.value)} className="w-20 text-right font-medium" />
            </div>
            <div className="flex justify-between">
              <span className="text-sm">Follow-through Bars</span>
              <input type="number" value={followBars} onChange={e => setFollowBars(+e.target.value)} className="w-20 text-right font-medium" />
            </div>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 text-lg font-semibold">🛡️ Risk & Setups</h3>
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={enableTrap} onChange={e => setEnableTrap(e.target.checked)} /> Trap
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={enableAbsorption} onChange={e => setEnableAbsorption(e.target.checked)} /> Absorption
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={enableSqueeze} onChange={e => setEnableSqueeze(e.target.checked)} /> Squeeze
              </label>
            </div>
            <div className="flex justify-between pt-2">
              <span className="text-sm">SL (ATR Mult)</span>
              <input type="number" step="0.1" value={slMult} onChange={e => setSlMult(+e.target.value)} className="w-20 text-right" />
            </div>
            <div className="flex justify-between">
              <span className="text-sm">TP (ATR Mult)</span>
              <input type="number" step="0.1" value={tpMult} onChange={e => setTpMult(+e.target.value)} className="w-20 text-right" />
            </div>
          </div>
        </div>
      </div>

      <div className="card p-4 bg-slate-50 border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="font-semibold text-ink">Level 3 MBO Engine</span>
            <span className="text-xs text-slate-500">
              {['NQ', 'ES'].includes(symbol) ? 'Use institutional tick-data from Databento' : 'Only available for NQ/ES'}
            </span>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input 
              type="checkbox" 
              className="sr-only peer" 
              disabled={!['NQ', 'ES'].includes(symbol)}
              checked={useMBO} 
              onChange={e => setUseMBO(e.target.checked)} 
            />
            <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-violet-600"></div>
          </label>
        </div>

        {useMBO && (
          <div className="mt-4 pt-4 border-t border-slate-200 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Test Date</span>
                <input 
                  type="date" 
                  value={startDate} 
                  onChange={e => setStartDate(e.target.value)}
                  className="p-2 border rounded bg-white text-xs"
                />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Start Time (UTC)</span>
                <input 
                  type="time" 
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                  className="p-2 border rounded bg-white text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-sm font-medium text-ink">Discovery Mode (Edge Hunter)</span>
                <span className="text-[10px] text-slate-500">Execute ALL signals to analyze performance</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" className="sr-only peer" checked={discoveryMode} onChange={e => setDiscoveryMode(e.target.checked)} />
                <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
              </label>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-sm font-medium text-ink">Strict Statistical Validation</span>
                <span className="text-[10px] text-slate-500">Only trade segments passing T-Stat &gt; 2.5 and Train/Test check</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" className="sr-only peer" checked={useValidation} onChange={e => setUseValidation(e.target.checked)} />
                <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>
          </div>
        )}
      </div>

      {loading && useMBO && (
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 capitalize">{jobStage.replace('_', ' ')}...</span>
            <span className="font-mono">{Math.round(progress * 100)}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div 
              className="bg-violet-600 h-full transition-all duration-500 ease-out" 
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          <button onClick={handleCancel} className="text-xs text-coral hover:underline w-full text-center">
            Cancel Processing
          </button>
        </div>
      )}

      <button onClick={handleRun} disabled={loading || (!useMBO && candles.length < 80)} className="btn-ink w-full py-4 text-lg">
        {loading ? (useMBO ? 'L3 Microstructure Pipeline...' : 'Analyzing Order Flow...') : `🚀 Start ${useMBO ? 'L3 MBO' : 'Fabio'} Backtest`}
      </button>

      {error && <p className="text-coral text-center">{error}</p>}
    </div>
  );
}

function FabioResults({ result, symbol, timeframe, period, session, candles, params, onBack }: any) {
  const [training, setTraining] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const [minConf, setMinConf] = useState(0);

  const filteredTrades = (result?.trades_list || []).filter((t: any) =>
    (t.confluence ?? 0) >= minConf
  );

  const handleTrain = async () => {
    setTraining(true);
    try {
      const res = await trainFabioAi({ trades: filteredTrades });
      setAiResult(res);
    } catch (err: any) {
      alert(err.message || 'Training failed');
    } finally {
      setTraining(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveFabioResult({
        symbol,
        timeframe,
        period,
        session_filter: session,
        result,
        params,
      });
      setSaved(true);
    } catch (err) {
      alert('Failed to save result');
    } finally {
      setSaving(false);
    }
  };

  const handleExportCSV = () => {
    const headers = ['#','Timestamp','Setup','Direction','Entry','SL','TP','Exit','Exit_Reason','Result','PnL_R','Bars','Confluence','Conf_Detail','Risk_Tier','Note'];
    const rows = filteredTrades.map((t: any, i: number) => [
      i+1, t.timestamp, t.setup, t.direction, t.entry, t.stop_loss,
      t.take_profit, t.exit_price, t.exit_reason ?? '', t.result, t.pnl_r, t.holding_bars,
      t.confluence ?? '', t.confluence_detail ?? '', t.risk_tier ?? '', t.note
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `fabio_${symbol}_${timeframe}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const gradeColor = (g: string) => {
    if (g === 'A') return 'bg-emerald-100 text-emerald-800';
    if (g === 'B') return 'bg-blue-100 text-blue-800';
    if (g === 'C') return 'bg-amber-100 text-amber-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold">📊 Fabio Strategy Results</h2>
          <span className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-600 font-mono">{symbol} · {timeframe} · {period}</span>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button 
            onClick={handleSave} 
            disabled={saving || saved}
            className={`py-2 px-3 text-xs rounded-lg font-medium transition ${saved ? 'bg-teal-100 text-teal-700 cursor-default' : 'bg-slate-100 hover:bg-slate-200'}`}
          >
            {saving ? 'Saving...' : saved ? '✅ Saved' : '💾 Save to History'}
          </button>
          <button onClick={handleExportCSV} className="py-2 px-3 text-xs rounded-lg bg-slate-100 hover:bg-slate-200 font-medium">
            📥 Export CSV
          </button>
          <button 
            onClick={handleTrain} 
            disabled={training || filteredTrades.length < 10}
            className={`py-2 px-3 text-xs rounded-lg font-medium transition ${filteredTrades.length < 10 ? 'bg-slate-50 text-slate-400 cursor-not-allowed' : 'bg-amber-100 hover:bg-amber-200 text-amber-800'}`}
            title={filteredTrades.length < 10 ? "Need at least 10 trades to train the model" : "Train ML model on these results"}
          >
            {training ? 'Training...' : `🧠 Train AI (${filteredTrades.length})`}
          </button>
          <button onClick={onBack} className="text-sea hover:underline text-sm">← New Test</button>
        </div>
      </div>

      {/* Confluence Filter */}
      <div className="card p-4 flex items-center gap-4 flex-wrap">
        <span className="text-sm font-medium">🎯 Min Confluence:</span>
        {[0,1,2,3,4,5].map(v => (
          <button key={v} onClick={() => setMinConf(v)}
            className={`w-8 h-8 rounded-full text-xs font-bold transition ${minConf === v ? 'bg-ink text-white' : 'bg-slate-100 hover:bg-slate-200'}`}>
            {v}
          </button>
        ))}
        <span className="text-xs text-slate-400 ml-auto">
          Showing {filteredTrades.length} / {(result?.trades_list || []).length} trades
        </span>
      </div>

      {/* ── AI Training Results ── */}
      {aiResult && (
        <div className="card p-5 bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200 space-y-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-amber-900">🧠 AI Pattern Analysis</h3>
            <div className="flex gap-3 text-xs text-amber-700">
              <span>Accuracy: <b>{(aiResult.metrics?.accuracy * 100).toFixed(1)}%</b></span>
              <span>Precision: <b>{(aiResult.metrics?.precision * 100).toFixed(1)}%</b></span>
              <span>Samples: <b>{aiResult.metrics?.samples}</b></span>
            </div>
          </div>

          {/* Insights */}
          {aiResult.insights?.length > 0 && (
            <div className="space-y-1">
              {aiResult.insights.map((ins: string, i: number) => (
                <p key={i} className="text-sm text-amber-800">{ins}</p>
              ))}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* Setup Breakdown */}
            {aiResult.setup_breakdown?.length > 0 && (
              <div className="bg-white/60 rounded-lg p-4">
                <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Setup Performance</h4>
                <div className="space-y-2">
                  {aiResult.setup_breakdown.map((s: any) => (
                    <div key={s.setup} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${gradeColor(s.grade)}`}>{s.grade}</span>
                        <span className="font-medium truncate max-w-[100px]">{s.setup}</span>
                      </div>
                      <div className="flex gap-2 text-slate-600">
                        <span>{s.trades} tr</span>
                        <span className="font-semibold">{s.win_rate}%</span>
                        <span className={s.total_r >= 0 ? 'text-emerald-600 font-bold' : 'text-red-500 font-bold'}>
                          {s.total_r > 0 ? '+' : ''}{s.total_r}R
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Session Breakdown */}
            {aiResult.session_breakdown?.length > 0 && (
              <div className="bg-white/60 rounded-lg p-4">
                <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Session Performance</h4>
                <div className="space-y-2">
                  {aiResult.session_breakdown.map((s: any) => (
                    <div key={s.session} className="flex items-center justify-between text-xs">
                      <span className="font-medium capitalize">{s.session}</span>
                      <div className="flex gap-2 text-slate-600">
                        <span>{s.trades} tr</span>
                        <span className="font-semibold">{s.win_rate}%</span>
                        <span className={s.total_r >= 0 ? 'text-emerald-600 font-bold' : 'text-red-500 font-bold'}>
                          {s.total_r > 0 ? '+' : ''}{s.total_r}R
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Feature Importance */}
            {aiResult.feature_importance?.length > 0 && (
              <div className="bg-white/60 rounded-lg p-4">
                <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">ML Feature Importance</h4>
                <div className="space-y-1.5">
                  {aiResult.feature_importance.slice(0, 6).map((f: any) => (
                    <div key={f.feature} className="text-xs">
                      <div className="flex justify-between mb-0.5">
                        <span className="font-medium truncate max-w-[120px]">{f.feature}</span>
                        <span className="text-amber-700">{(f.importance * 100).toFixed(0)}%</span>
                      </div>
                      <div className="w-full bg-amber-100 rounded-full h-1.5">
                        <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${Math.min(f.importance * 100 / (aiResult.feature_importance[0]?.importance || 1) * 100, 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Hour Heatmap */}
          {aiResult.hour_breakdown?.length > 0 && (
            <div className="bg-white/60 rounded-lg p-4">
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Hour Heatmap (UTC)</h4>
              <div className="flex flex-wrap gap-1">
                {aiResult.hour_breakdown.map((h: any) => {
                  const maxR = Math.max(...aiResult.hour_breakdown.map((x: any) => Math.abs(x.total_r)), 1);
                  const intensity = Math.min(Math.abs(h.total_r) / maxR, 1);
                  const bg = h.total_r >= 0 
                    ? `rgba(16, 185, 129, ${0.15 + intensity * 0.7})` 
                    : `rgba(239, 68, 68, ${0.15 + intensity * 0.7})`;
                  return (
                    <div key={h.hour} 
                      className="flex flex-col items-center justify-center rounded px-2 py-1 text-[10px] min-w-[40px]"
                      style={{ background: bg }}
                      title={`${h.hour}:00 UTC — ${h.trades} trades, ${h.win_rate}% WR, ${h.total_r}R`}
                    >
                      <span className="font-bold">{h.hour}h</span>
                      <span>{h.total_r > 0 ? '+' : ''}{h.total_r}R</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Score Summary */}
      {result.has_ai_scores && (
        <div className="card p-4 bg-gradient-to-r from-violet-50 to-purple-50 border-violet-200">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">🤖</span>
              <span className="text-sm font-bold text-violet-900">AI Score Active</span>
              <span className="text-xs text-violet-600">({result.ai_scored_trades} trades scored, avg {result.ai_avg_score}%)</span>
            </div>
            <div className="flex gap-4 text-xs">
              <span className="text-emerald-700 font-semibold">
                Score ≥60%: {result.ai_high_score_trades} trades → <b>{result.ai_high_score_wr}% WR</b>
              </span>
              <span className="text-red-600 font-semibold">
                Score &lt;40%: {result.ai_low_score_trades} trades → <b>{result.ai_low_score_wr}% WR</b>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Row 1: Core Stats */}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
        <div className="card p-4 text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Win Rate</p>
          <p className={`text-2xl font-bold ${result.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{result.win_rate}%</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Profit Factor</p>
          <p className="text-2xl font-bold">{result.profit_factor}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Total R</p>
          <p className={`text-2xl font-bold ${result.total_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{result.total_r > 0 ? '+' : ''}{result.total_r}R</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider">Return</p>
          <p className={`text-2xl font-bold ${result.return_pct > 0 ? 'text-teal-600' : 'text-red-500'}`}>{result.return_pct > 0 ? '+' : ''}{result.return_pct}%</p>
        </div>
      </div>

      {/* Row 2: Advanced Stats */}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-6">
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Trades</p>
          <p className="text-lg font-bold">{result?.total_trades}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Expectancy</p>
          <p className="text-lg font-bold">{result?.expectancy_r}R</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Sharpe</p>
          <p className="text-lg font-bold">{result?.sharpe_ratio}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Sortino</p>
          <p className="text-lg font-bold">{result?.sortino_ratio}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Max DD</p>
          <p className="text-lg font-bold text-red-500">{result?.max_drawdown_r}R</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[9px] text-slate-400 uppercase">Avg Hold</p>
          <p className="text-lg font-bold">{result?.avg_holding_bars} bars</p>
        </div>
      </div>

      {/* Equity Curve */}
      <div className="card p-5">
        <h3 className="mb-4 font-semibold">📈 Equity Curve (R-multiple)</h3>
        <EquityCurve points={result?.equity_curve || []} />
      </div>

      {/* Setup Breakdown + Insights */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-4 font-semibold">🎯 Setup Breakdown</h3>
          <div className="space-y-2">
            {(result?.setup_breakdown || []).map((s: any) => (
              <div key={s.setup} className="flex justify-between items-center bg-slate-50 p-3 rounded-lg text-sm">
                <span className="font-medium uppercase text-xs">{s.setup.replaceAll('_', ' ')}</span>
                <div className="text-right text-xs">
                  <span className="text-slate-500">{s.trades}t </span>
                  <span className={`font-bold ${s.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{s.win_rate}%</span>
                  <span className="text-slate-400"> | </span>
                  <span className={`font-bold ${s.pnl_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{s.pnl_r > 0 ? '+' : ''}{s.pnl_r}R</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-5">
          <h3 className="mb-4 font-semibold">💡 Strategy Insights</h3>
          <ul className="space-y-2 text-sm text-slate-600">
            {(result?.notes || []).map((n: string, i: number) => <li key={i}>• {n}</li>)}
          </ul>
        </div>
      </div>

      {/* Exit Reason + Risk Tier Breakdown */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-4 font-semibold">🚪 Exit Reasons</h3>
          <div className="space-y-2">
            {(result?.exit_breakdown || []).map((e: any) => {
              const labels: Record<string, string> = {
                sl: '🛑 Stop Loss', tp: '✅ Take Profit', cvd_exit: '📊 CVD Exit',
                de_exit: '⚡ Deep Effort Exit', bt_trail: '📈 BT Trail', timeout: '⏱️ Timeout',
              };
              return (
                <div key={e.reason} className="flex justify-between items-center bg-slate-50 p-3 rounded-lg text-sm">
                  <span className="font-medium text-xs">{labels[e.reason] || e.reason}</span>
                  <div className="text-right text-xs">
                    <span className="text-slate-500">{e.trades}t </span>
                    <span className={`font-bold ${e.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{e.win_rate}%</span>
                    <span className="text-slate-400"> | </span>
                    <span className={`font-bold ${e.pnl_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{e.pnl_r > 0 ? '+' : ''}{e.pnl_r}R</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="card p-5">
          <h3 className="mb-4 font-semibold">💰 Risk Tiers (Confluence)</h3>
          <div className="space-y-2">
            {(result?.tier_breakdown || []).map((t: any) => {
              const tierLabels: Record<string, string> = {
                standard: '🟢 Standard (0.25%)', elevated: '🟡 Elevated (0.5%)', max: '🔴 Max (Day Profit)',
              };
              return (
                <div key={t.tier} className="flex justify-between items-center bg-slate-50 p-3 rounded-lg text-sm">
                  <span className="font-medium text-xs">{tierLabels[t.tier] || t.tier}</span>
                  <div className="text-right text-xs">
                    <span className="text-slate-500">{t.trades}t </span>
                    <span className={`font-bold ${t.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{t.win_rate}%</span>
                    <span className="text-slate-400"> | </span>
                    <span className={`font-bold ${t.pnl_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{t.pnl_r > 0 ? '+' : ''}{t.pnl_r}R</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Monthly Breakdown + Hourly Heatmap */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Monthly */}
        <div className="card overflow-hidden">
          <div className="bg-slate-50 px-5 py-3 border-b border-slate-100">
            <h3 className="font-semibold">📅 Monthly Performance</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-100 text-slate-500">
                <tr>
                  <th className="p-2 text-left">Month</th>
                  <th className="p-2">Trades</th>
                  <th className="p-2">WR</th>
                  <th className="p-2">PnL</th>
                </tr>
              </thead>
              <tbody>
                {(result?.monthly_breakdown || []).map((m: any) => (
                  <tr key={m.month} className="border-t border-slate-100">
                    <td className="p-2 font-mono">{m.month}</td>
                    <td className="p-2 text-center">{m.trades}</td>
                    <td className={`p-2 text-center font-bold ${m.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{m.win_rate}%</td>
                    <td className={`p-2 text-center font-bold ${m.pnl_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{m.pnl_r > 0 ? '+' : ''}{m.pnl_r}R</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Hourly Heatmap */}
        <div className="card p-5">
          <h3 className="mb-4 font-semibold">🕐 Hour Heatmap (UTC+5)</h3>
          <div className="grid grid-cols-6 gap-1">
            {(result?.hourly_breakdown || []).map((h: any) => {
              const intensity = Math.min(1, Math.abs(h.pnl_r) / 5);
              const bg = h.pnl_r > 0
                ? `rgba(20, 184, 166, ${0.15 + intensity * 0.6})`
                : `rgba(239, 68, 68, ${0.15 + intensity * 0.6})`;
              return (
                <div key={h.hour} className="rounded-lg p-2 text-center" style={{ background: bg }}>
                  <p className="text-[10px] font-bold">{String(h.hour).padStart(2, '0')}:00</p>
                  <p className="text-[9px]">{h.trades}t</p>
                  <p className={`text-[10px] font-bold ${h.pnl_r > 0 ? 'text-teal-800' : 'text-red-800'}`}>
                    {h.pnl_r > 0 ? '+' : ''}{h.pnl_r}R
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Walk-Forward Indicator */}
      <div className="card p-5">
        <h3 className="mb-3 font-semibold">🔬 Walk-Forward Check</h3>
        {(() => {
          const trades = filteredTrades;
          if (trades.length < 10) return <p className="text-sm text-slate-400">Need 10+ trades for walk-forward check.</p>;
          const mid = Math.floor(trades.length / 2);
          const firstHalf = trades.slice(0, mid);
          const secondHalf = trades.slice(mid);
          const wrFirst = (firstHalf.filter((t: any) => t.result === 'win').length / firstHalf.length * 100).toFixed(1);
          const wrSecond = (secondHalf.filter((t: any) => t.result === 'win').length / secondHalf.length * 100).toFixed(1);
          const pnlFirst = firstHalf.reduce((s: number, t: any) => s + t.pnl, 0).toFixed(2);
          const pnlSecond = secondHalf.reduce((s: number, t: any) => s + t.pnl, 0).toFixed(2);
          const isStable = Math.abs(+wrFirst - +wrSecond) < 15;
          return (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div></div>
                <div className="font-bold text-slate-600">1st Half ({firstHalf.length}t)</div>
                <div className="font-bold text-slate-600">2nd Half ({secondHalf.length}t)</div>
                <div className="text-left font-medium">Win Rate</div>
                <div className={+wrFirst > 50 ? 'text-teal-600 font-bold' : 'text-red-500 font-bold'}>{wrFirst}%</div>
                <div className={+wrSecond > 50 ? 'text-teal-600 font-bold' : 'text-red-500 font-bold'}>{wrSecond}%</div>
                <div className="text-left font-medium">PnL</div>
                <div className={+pnlFirst > 0 ? 'text-teal-600 font-bold' : 'text-red-500 font-bold'}>{+pnlFirst > 0 ? '+' : ''}{pnlFirst}R</div>
                <div className={+pnlSecond > 0 ? 'text-teal-600 font-bold' : 'text-red-500 font-bold'}>{+pnlSecond > 0 ? '+' : ''}{pnlSecond}R</div>
              </div>
              <div className={`p-3 rounded-lg text-sm font-medium text-center ${isStable ? 'bg-teal-50 text-teal-700' : 'bg-red-50 text-red-700'}`}>
                {isStable
                  ? '✅ Strategy is consistent — results hold across both halves. Low overfitting risk.'
                  : '⚠️ Performance diverges between halves — possible overfitting. Adjust parameters.'}
              </div>
            </div>
          );
        })()}
      </div>

      {/* NEW: TradingView Chart Section */}
      <div className="mb-8">
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
              L3 Execution Chart (TradingView)
            </h3>
            <span className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">{symbol.replace('.FUT', '')} • {timeframe} • MBO DATA</span>
          </div>
          <FabioChart candles={candles} trades={result?.trades_list || []} />
        </div>
      </div>

      {/* Full Trade Log */}
      <div className="card overflow-hidden">
        <div className="bg-slate-50 px-5 py-3 border-b border-slate-100">
          <h3 className="font-semibold">📜 Trade Log ({filteredTrades.length} trades)</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-100 text-slate-500 text-left">
              <tr>
                <th className="p-2">#</th>
                <th className="p-2">Time (UTC+5)</th>
                <th className="p-2">Setup</th>
                <th className="p-2">Dir</th>
                <th className="p-2">Entry</th>
                <th className="p-2">SL</th>
                <th className="p-2">TP</th>
                <th className="p-2">Exit</th>
                <th className="p-2">Why</th>
                <th className="p-2">Result</th>
                <th className="p-2">PnL</th>
                <th className="p-2">Bars</th>
                <th className="p-2">Conf</th>
                <th className="p-2">Tier</th>
                <th className="p-2">AI</th>
                <th className="p-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t: any, i: number) => (
                <tr key={i} className={`border-t border-slate-100 ${t.result === 'win' ? 'bg-teal-50/30' : 'bg-red-50/30'}`}>
                  <td className="p-2 text-slate-400">{i + 1}</td>
                  <td className="p-2 font-mono text-[10px] text-slate-500 whitespace-nowrap">
                    {t.time}
                  </td>
                  <td className="p-2 font-semibold uppercase whitespace-nowrap">{t.setup.replaceAll('_', ' ')}</td>
                  <td className="p-2">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${t.dir === 'Long' ? 'bg-teal-100 text-teal-700' : 'bg-violet-100 text-violet-700'}`}>
                      {t.dir.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-2 font-mono">{t.entry}</td>
                  <td className="p-2 font-mono text-red-400">{t.sl}</td>
                  <td className="p-2 font-mono text-teal-500">{t.tp}</td>
                  <td className="p-2 font-mono">{t.exit}</td>
                  <td className="p-2">
                    {t.why && (
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        t.why === 'tp' ? 'bg-teal-100 text-teal-700' :
                        t.why === 'sl' ? 'bg-red-100 text-red-700' :
                        t.why === 'cvd_exit' ? 'bg-blue-100 text-blue-700' :
                        t.why === 'de_exit' ? 'bg-purple-100 text-purple-700' :
                        t.why === 'bt_trail' ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-500'
                      }`}>
                        {t.why === 'tp' ? 'TP' : t.why === 'sl' ? 'SL' :
                         t.why === 'cvd_exit' ? 'CVD' : t.why === 'de_exit' ? 'DE' :
                         t.why === 'bt_trail' ? 'BT' : 'TIME'}
                      </span>
                    )}
                  </td>
                  <td className="p-2">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${t.result === 'win' ? 'bg-teal-100 text-teal-700' : 'bg-red-100 text-red-700'}`}>
                      {t.result.toUpperCase()}
                    </span>
                  </td>
                  <td className={`p-2 font-bold ${t.pnl > 0 ? 'text-teal-600' : 'text-red-500'}`}>
                    {t.pnl > 0 ? '+' : ''}{t.pnl}R
                  </td>
                  <td className="p-2 text-slate-400">{t.bars}</td>
                  <td className="p-2">
                    {t.conf !== undefined && (
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${t.conf >= 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>
                        {t.conf}/5
                      </span>
                    )}
                  </td>
                  <td className="p-2">
                    {t.tier && (
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        t.tier === 'max' ? 'bg-red-100 text-red-700' :
                        t.tier === 'elevated' ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-500'
                      }`}>
                        {t.tier === 'max' ? '🔴' : t.tier === 'elevated' ? '🟡' : '🟢'}
                      </span>
                    )}
                  </td>
                  <td className="p-2">
                    {t.ai_score >= 0 && (
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        t.ai_score >= 60 ? 'bg-emerald-100 text-emerald-700' :
                        t.ai_score >= 40 ? 'bg-amber-100 text-amber-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {t.ai_score}%
                      </span>
                    )}
                  </td>
                  <td className="p-2 text-[10px] text-slate-400 max-w-[200px] truncate" title={t.note}>{t.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function FabioHistory({ onBack, onSelect }: any) {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFabioHistory()
      .then(setHistory)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">📜 Saved Fabio Tests</h2>
        <button onClick={onBack} className="text-sea hover:underline text-sm">← Back to Setup</button>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="p-4">Date</th>
                <th className="p-4">Symbol</th>
                <th className="p-4">Timeframe</th>
                <th className="p-4">Trades</th>
                <th className="p-4">Win Rate</th>
                <th className="p-4">Total PnL</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="p-10 text-center text-slate-400">Loading history...</td></tr>
              ) : history.length === 0 ? (
                <tr><td colSpan={7} className="p-10 text-center text-slate-400">No saved tests yet.</td></tr>
              ) : history.map((h: any) => (
                <tr key={h.id} className="border-t border-slate-100 hover:bg-slate-50 transition">
                  <td className="p-4 text-xs text-slate-500">
                    {new Date(h.created_at).toLocaleDateString()} {new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="p-4 font-bold">{h.symbol}</td>
                  <td className="p-4">{h.timeframe} ({h.period})</td>
                  <td className="p-4 text-slate-500">{h.total_trades}</td>
                  <td className={`p-4 font-bold ${h.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>
                    {h.win_rate}%
                  </td>
                  <td className={`p-4 font-bold ${h.total_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>
                    {h.total_r > 0 ? '+' : ''}{h.total_r}R
                  </td>
                  <td className="p-4 text-right">
                    <button 
                      onClick={() => onSelect(h)}
                      className="px-3 py-1 rounded bg-ink text-white text-xs font-medium hover:bg-slate-800"
                    >
                      Open Report
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function FabioAiMemory({ onBack }: { onBack: () => void }) {
  const [memory, setMemory] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    import('@/lib/api').then(({ getFabioMemory }) => {
      getFabioMemory()
        .then(res => setMemory(res))
        .catch(err => setError(err.message || 'Failed to load memory'))
        .finally(() => setLoading(false));
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition">
          ←
        </button>
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">🧠 AI Memory & Insights</h2>
          <p className="text-sm text-slate-500">Accumulated learnings from all training sessions</p>
        </div>
      </div>

      {loading ? (
        <div className="card p-10 flex justify-center"><div className="w-8 h-8 border-4 border-ink border-t-transparent rounded-full animate-spin"></div></div>
      ) : error ? (
        <div className="card p-10 text-center text-red-500 bg-red-50 border-red-100">{error}</div>
      ) : !memory?.total_sessions ? (
        <div className="card p-10 text-center text-slate-500">
          <p className="text-4xl mb-4">🤖</p>
          <p className="font-medium text-lg text-ink mb-1">AI has no memories yet</p>
          <p className="text-sm">Run backtests and click "Train AI" to start accumulating knowledge.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 grid-cols-3">
            <div className="card p-5 bg-gradient-to-br from-violet-50 to-purple-50 border-violet-100">
              <p className="text-xs font-semibold text-violet-600 uppercase tracking-wider mb-1">Total Training Sessions</p>
              <p className="text-3xl font-bold text-violet-900">{memory.total_sessions}</p>
            </div>
            <div className="card p-5 bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-100">
              <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-1">Trades Analyzed</p>
              <p className="text-3xl font-bold text-blue-900">{memory.total_trades_analyzed}</p>
            </div>
            <div className="card p-5 bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-100">
              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-1">Model Status</p>
              <p className="text-3xl font-bold text-emerald-900">
                {memory.has_model ? '✅ Active' : '❌ Missing'}
              </p>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* Cumulative Rules */}
            <div className="card p-5">
              <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                <span>📖</span> The Playbook
              </h3>
              <p className="text-xs text-slate-500 mb-4">Rules AI generated based on your history:</p>
              <div className="space-y-3">
                {memory.cumulative_recommendations?.map((rec: string, i: number) => (
                  <div key={i} className="flex gap-3 text-sm p-3 bg-slate-50 rounded-lg">
                    <span>{rec}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Lifetime Setup Performance */}
            <div className="card p-5">
              <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                <span>📊</span> Lifetime Setup Performance
              </h3>
              <div className="space-y-3">
                {memory.lifetime_setup_performance?.map((s: any) => (
                  <div key={s.setup} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg text-sm">
                    <span className="font-semibold uppercase">{s.setup.replaceAll('_', ' ')}</span>
                    <div className="flex gap-4 text-right">
                      <span className="text-slate-500 w-16">{s.total_trades}t</span>
                      <span className={`w-12 font-bold ${s.win_rate > 50 ? 'text-teal-600' : 'text-red-500'}`}>{s.win_rate}%</span>
                      <span className={`w-16 font-bold ${s.total_r > 0 ? 'text-teal-600' : 'text-red-500'}`}>{s.total_r > 0 ? '+' : ''}{s.total_r}R</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function FabioEdgeAnalysis({ onBack }: { onBack: () => void }) {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFabioL3Analysis().then(setReport).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-20 text-center animate-pulse text-ink">Gathering statistical evidence...</div>;
  if (!report || report.error || report.detail || !report.summary) {
    return (
      <div className="p-20 text-center space-y-4">
        <div className="text-4xl">🔬</div>
        <p className="text-slate-500 font-medium">{report?.error || report?.detail || 'No analysis available yet.'}</p>
        <p className="text-xs text-slate-400">Run at least 10 trades in Discovery Mode to generate an Edge Report.</p>
        <button onClick={onBack} className="btn-secondary px-6">Back to Dashboard</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </button>
        <h2 className="text-2xl font-bold">🛡️ Edge Stability Dashboard</h2>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        <div className="card p-5 bg-violet-50 border-violet-100">
          <span className="text-xs text-violet-500 font-bold uppercase tracking-wider">Total Trades</span>
          <div className="text-3xl font-black text-violet-900">{report.summary.total_trades}</div>
        </div>
        <div className="card p-5 bg-teal-50 border-teal-100">
          <span className="text-xs text-teal-500 font-bold uppercase tracking-wider">Historical WR</span>
          <div className="text-3xl font-black text-teal-900">{report.summary.win_rate}%</div>
        </div>
        <div className="card p-5 bg-slate-50 border-slate-100">
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">Score Correlation</span>
          <div className="text-3xl font-black text-slate-900">{report.summary.score_correlation}</div>
        </div>
        <div className="card p-5 bg-indigo-50 border-indigo-100">
          <span className="text-xs text-indigo-500 font-bold uppercase tracking-wider">Decay Status</span>
          <div className={`text-xl font-black uppercase ${report.summary.decay_status === 'decaying' ? 'text-rose-600' : 'text-emerald-600'}`}>
            {report.summary.decay_status}
          </div>
        </div>
      </div>

      {report.summary.decay_status === 'decaying' && (
        <div className="p-4 bg-rose-100 border border-rose-200 text-rose-800 rounded-xl font-bold flex items-center gap-3 animate-pulse">
          <span>⚠️</span> {report.summary.decay_alert}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2">🌐 Regime Performance Map</h3>
          <div className="space-y-4">
            {Object.entries(report.regime_performance || {}).map(([name, data]: any) => (
              <div key={name} className="flex items-center gap-4">
                <div className="w-32 text-xs font-bold uppercase text-slate-500 truncate">{name.replaceAll('_', ' ')}</div>
                <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden flex">
                  <div 
                    className={`${data.avg_R > 0 ? 'bg-emerald-500' : 'bg-rose-500'} h-full`}
                    style={{ width: `${Math.min(100, Math.abs(data.avg_R) * 50)}%` }}
                  />
                </div>
                <div className={`w-16 text-right font-black text-sm ${data.avg_R > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {data.avg_R > 0 ? '+' : ''}{data.avg_R.toFixed(2)}R
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2">📈 Expectancy Stability (ST vs LT)</h3>
          <div className="h-40 flex items-end gap-1">
            {report.rolling_expectancy.long_term.map((v: number, i: number) => (
              <div key={i} className="flex-1 flex flex-col justify-end gap-0.5 group relative">
                <div className="w-full bg-slate-200 rounded-t-sm" style={{ height: `${Math.max(10, (v + 1) * 30)}%` }} />
                <div 
                  className="w-full bg-indigo-500 rounded-t-sm absolute bottom-0 opacity-60" 
                  style={{ height: `${Math.max(10, (report.rolling_expectancy.short_term[i] + 1) * 30)}%` }} 
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-[10px] text-slate-400 font-bold uppercase">
            <span>Historical Baseline</span>
            <span>Recent Performance</span>
          </div>
        </div>
      </div>

      <div className="card p-6 border-indigo-200 bg-indigo-50/20">
        <h3 className="text-lg font-bold text-indigo-900 mb-4">🛡️ Statistically Stable Segments (t {'>'} 2.5)</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(report.validated_edge).map(([key, data]: any) => (
            <div key={key} className="flex justify-between items-center p-4 bg-white rounded-xl border border-indigo-100 shadow-sm">
              <div className="flex-1 min-w-0">
                <div className="font-bold text-[10px] uppercase text-slate-400 truncate">{key.replaceAll('|', ' • ')}</div>
                <div className="flex gap-2 mt-1">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${data.stability_score > 0.7 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    Stability {Math.round(data.stability_score * 100)}%
                  </span>
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px] font-bold">{data.count} trades</span>
                </div>
              </div>
              <div className="text-right ml-4">
                <div className="text-lg font-black text-indigo-600">t={data.t_stat.toFixed(1)}</div>
                <div className="text-[10px] text-slate-400">Exp: {data.expectancy.toFixed(2)}R</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-6 border-emerald-200 bg-emerald-50/30">
          <h3 className="text-lg font-bold text-emerald-900 mb-4 flex items-center gap-2">
            ✅ Top Profitable Segments
          </h3>
          <div className="space-y-3">
            {(report.profitable_segments || []).map((s: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-3 bg-white rounded-lg border border-emerald-100 shadow-sm">
                <div>
                  <div className="font-bold text-sm uppercase">{s.event_type} @ {s.location}</div>
                  <div className="text-[10px] text-slate-500">{s.session} session | {s.count} samples</div>
                </div>
                <div className="text-right">
                  <div className="text-emerald-600 font-black">+{s.avg_R.toFixed(2)}R</div>
                  <div className="text-[10px] font-bold text-slate-400">{s.win_rate.toFixed(0)}% WR</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6 border-red-200 bg-red-50/30">
          <h3 className="text-lg font-bold text-red-900 mb-4 flex items-center gap-2">
            🚫 Toxic / Losing Segments
          </h3>
          <div className="space-y-3">
            {(report.toxic_segments || []).map((s: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-3 bg-white rounded-lg border border-red-100 shadow-sm">
                <div>
                  <div className="font-bold text-sm uppercase">{s.event_type} @ {s.location}</div>
                  <div className="text-[10px] text-slate-500">{s.session} session | {s.count} samples</div>
                </div>
                <div className="text-right">
                  <div className="text-red-600 font-black">{s.avg_R.toFixed(2)}R</div>
                  <div className="text-[10px] font-bold text-slate-400">{s.win_rate.toFixed(0)}% WR</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-bold mb-4">🧠 Score Validation: Conviction vs Outcome</h3>
        <div className="flex items-end gap-2 h-48 pt-10">
          {Object.entries(report.score_validation || {}).map(([bin, val]: any) => (
            <div key={bin} className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-violet-100 rounded-t-lg relative group" style={{ height: `${Math.max(20, (val + 1) * 40)}%` }}>
                <div className={`absolute inset-0 rounded-t-lg ${val > 0 ? 'bg-teal-500' : 'bg-rose-500'} opacity-70`} />
                <div className="absolute -top-6 left-0 right-0 text-center text-[10px] font-bold">{val.toFixed(2)}R</div>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">{bin}</span>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm text-slate-500 bg-slate-50 p-4 rounded-lg italic">
          💡 This chart validates your scoring algorithm. Profitable bars in high-score bins (0.8-1.0) confirm that the engine accurately identifies conviction.
        </p>
      </div>

      <div className="card p-6 bg-slate-900 text-white rounded-2xl shadow-2xl">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <span className="text-violet-400">🎯</span>
          <span>Edge Discovery Insights</span>
        </h3>
        <ul className="space-y-3">
          {(report.key_insights || []).map((insight: string, i: number) => (
            <li key={i} className="text-sm flex gap-3 p-2 hover:bg-slate-800 rounded-lg transition-colors">
              <span className="text-violet-400 font-bold opacity-50">0{i+1}</span>
              <span className="text-slate-200">{insight}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
